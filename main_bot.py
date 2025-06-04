import pytz
import os
import re
import datetime
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_sdk.web import WebClient
from redis_bot import (
    set_thread_ts, record_task, get_thread_ts,
    generate_message_from_redis, get_task_deadlines, find_task_in_text
)

# ENV: SLACK_BOT_TOKEN, SLACK_APP_TOKEN, SLACK_CHANNEL_ID
app = App(token=os.environ.get("SLACK_APP_TOKEN"))
client = WebClient(token=os.environ.get("SLACK_BOT_TOKEN"))
CHANNEL_ID = os.environ.get("SLACK_CHANNEL_ID")

def generate_message(day_override=None):
    #Генерировать сообщение для debug режима
    # Получаем сообщение из Redis с поддержкой debug режима
    message = generate_message_from_redis(day_override=day_override, debug_mode=True)

    # Fallback к старой логике если Redis пуст
    if "_Нет задач на сегодня_" in message:
        print("⚠️ Задачи не найдены в Redis, используем старую логику")
        today = datetime.datetime.now()

        if day_override:
            day_name = day_override.capitalize()
            fake_date = today.strftime('%d %B') + f" ({day_name})"
        else:
            day_name = today.strftime('%A')
            fake_date = today.strftime('%d %B (%A)')

        if day_name == "Monday":
            tasks = [
                "- [ ] Statements",
                "- [ ] LPB до 12:00",
                "- [ ] Проверка KYC-1 до 11:00",
                "- [ ] Проверка KYC-2 после 15:00"
            ]
        else:
            tasks = [
                "- [ ] LPB до 12:00",
                "- [ ] Проверка KYC-1 до 11:00",
                "- [ ] Проверка KYC-2 после 15:00"
            ]

        header = f"🔧 DEBUG: 🎓 Routine tasks for *{fake_date}*"
        return header + "\n\n" + "\n".join(tasks)

    return message

@app.event("app_mention")
def handle_task_update(event, say):
    print("👀 BOT GOT MENTION:", event)  # ← отладка
    text = event.get("text", "")
    user = event.get("user")
    thread_ts = event.get("thread_ts") or event.get("ts")
    riga = pytz.timezone("Europe/Riga")
    ts = datetime.datetime.now(riga)

    # Debug command to simulate cron task
    if "debug" in text.lower():
        debug_text = text.lower()
        day_override = "Monday" if "monday" in debug_text else None
        message = generate_message(day_override=day_override)

        response = client.chat_postMessage(channel=CHANNEL_ID, text=message)
        # Используем debug режим для thread_ts
        set_thread_ts(response["ts"], debug_mode=True)
        say(text=f"<@{user}> отправлено сообщение с задачами (debug mode)", thread_ts=response["ts"])
        return
    #########################################

    # Определяем, это debug режим или обычный
    debug_mode = False
    debug_thread_ts = get_thread_ts(debug_mode=True)

    if thread_ts == debug_thread_ts:
        debug_mode = True
        print("🔧 DEBUG MODE: используем debug_routine_state")

    task = find_task_in_text(text)
    if task:
        ok, msg = record_task(task, user, debug_mode=debug_mode)
        if not ok:
            say(text=f"<@{user}> {msg}", thread_ts=thread_ts)
            return

        # Получаем дедлайны из Redis
        task_deadlines = get_task_deadlines()
        deadline = task_deadlines.get(task)

        if deadline:
            deadline_dt = riga.localize(datetime.datetime.combine(ts.date(), deadline))
            print(f"⏱️ Сейчас: {ts.strftime('%H:%M:%S')} | Дедлайн для {task}: {deadline_dt.strftime('%H:%M:%S')}")

            if ts > deadline_dt:
                prefix = "🔧 DEBUG: " if debug_mode else ""
                say(text=f"{prefix}<@{user}> {task} было сделано поздно!", thread_ts=thread_ts)
            else:
                client.reactions_add(channel=event["channel"], timestamp=event["ts"], name="white_check_mark")
        else:
            # Для задач без дедлайна просто ставим галочку
            client.reactions_add(channel=event["channel"], timestamp=event["ts"], name="white_check_mark")
    else:
        prefix = "🔧 DEBUG: " if debug_mode else ""
        say(text=f"{prefix}<@{user}> я не понял, о какой задаче речь 🤔. Напиши, например: `@bot LPB done`", thread_ts=thread_ts)

if __name__ == "__main__":
    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()
