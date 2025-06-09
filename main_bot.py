import pytz
import datetime
from typing import Dict, Any, Optional
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_sdk.web import WebClient
from config import Config
from redis_bot import (
    set_thread_ts, record_task, get_thread_ts,
    generate_message_from_redis, get_task_deadlines, find_task_in_text
)

# Setup logging and validate config
logger = Config.setup_logging()
Config.validate_required_env_vars()

# Initialize Slack app
app = App(token=Config.SLACK_APP_TOKEN)
client = WebClient(token=Config.SLACK_BOT_TOKEN)

def generate_message(day_override: Optional[str] = None) -> str:
    #Generate message for debug mode.
    try:
        # Get message from Redis with debug mode support
        message = generate_message_from_redis(day_override=day_override, debug_mode=True)

        # Empty Redis
        if "_Нет задач на сегодня_" in message:
            logger.warning("Tasks not found in Redis, using fallback logic")
        return message

    except Exception as e:
        logger.error(f"Error generating debug message: {e}")
        return "❌ Error generating debug message"

@app.event("app_mention")
def handle_task_update(event: Dict[str, Any], say) -> None:
    #Handle app mentions for task completion and debug commands.
    try:
        logger.info(f"Bot mentioned: {event.get('user')} - {event.get('text', '')}")

        text = event.get("text", "")
        user = event.get("user")
        thread_ts = event.get("thread_ts") or event.get("ts")
        riga = pytz.timezone(Config.TIMEZONE)
        ts = datetime.datetime.now(riga)

        # Debug command to simulate cron task
        if "debug" in text.lower():
            try:
                debug_text = text.lower()
                day_override = "Monday" if "monday" in debug_text else None
                message = generate_message(day_override=day_override)

                response = client.chat_postMessage(channel=Config.SLACK_CHANNEL_ID, text=message)
                # Use debug mode for thread_ts
                set_thread_ts(response["ts"], debug_mode=True)
                say(text=f"<@{user}> sent task message (debug mode)", thread_ts=response["ts"])
                logger.info(f"Debug message sent by user {user}")
                return
            except Exception as e:
                logger.error(f"Error handling debug command: {e}")
                say(text=f"<@{user}> ❌ Error sending debug message", thread_ts=thread_ts)
                return

        # Определяем, это debug режим или обычный (ПЕРЕНЕСЕНО ВНУТРЬ TRY)
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

    except Exception as e:
        logger.error(f"Error in handle_task_update: {e}")
        say(text=f"<@{user}> ❌ Произошла ошибка при обработке команды", thread_ts=thread_ts)


if __name__ == "__main__":
    SocketModeHandler(app, Config.SLACK_APP_TOKEN).start()
