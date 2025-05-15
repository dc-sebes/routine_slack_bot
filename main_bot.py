import os
import re
import datetime
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_sdk.web import WebClient

# ENV: SLACK_BOT_TOKEN, SLACK_APP_TOKEN, SLACK_CHANNEL_ID
app = App(token=os.environ.get("SLACK_BOT_TOKEN"))
client = WebClient(token=os.environ.get("SLACK_BOT_TOKEN"))
CHANNEL_ID = os.environ.get("SLACK_CHANNEL_ID")

#debug
def generate_message(day_override=None):
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

    header = f"🎓 Routine tasks for *{fake_date}*"
    return header + "\n\n" + "\n".join(tasks)

task_deadlines = {
    "LPB": datetime.time(hour=12),
    "KYC-1": datetime.time(hour=11),
    "KYC-2": datetime.time(hour=16),
}

@app.event("app_mention")
def handle_task_update(event, say):
    print("👀 BOT GOT MENTION:", event)  # ← отладка
    text = event.get("text", "")
    user = event.get("user")
    thread_ts = event.get("thread_ts") or event.get("ts")
    ts = datetime.datetime.now()

 # Debug command to simulate cron task
    if "debug" in text.lower():
     if "monday" in text.lower():
         message = generate_message(day_override="Monday")
     else:
         message = generate_message()

     client.chat_postMessage(channel=CHANNEL_ID, text=message)
     say(text=f"<@{user}> отправлено сообщение с задачами (debug mode)", thread_ts=thread_ts)
     return

    match = re.search(r"(?i)(LPB|KYC-1|KYC-2|Statements).*done", text)
    if match:
        task = match.group(1).upper()
        deadline = task_deadlines.get(task)
        if deadline:
                    deadline_dt = datetime.datetime.combine(ts.date(), deadline)
                    print(f"⏱️ Сейчас: {ts.strftime('%H:%M:%S')} | Дедлайн для {task}: {deadline_dt.strftime('%H:%M:%S')}")
                    if ts > deadline_dt:
                        say(text=f"<@{user}> {task} было сделано поздно!", thread_ts=thread_ts)
                    else:
                        client.reactions_add(channel=event["channel"], timestamp=event["ts"], name="white_check_mark")
        else:
         say(text=f"<@{user}> я не понял, о какой задаче речь 🤔. Напиши, например: `@bot LPB done`", thread_ts=thread_ts)




if __name__ == "__main__":
    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()
