import pytz
import datetime
from typing import Dict, Any, Optional
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from config import Config
from redis_bot import (
    set_thread_ts, record_task, get_thread_ts,
    generate_message_from_redis, get_task_deadlines, find_task_in_text
)

# Setup logging and validate config
logger = Config.setup_logging()
Config.validate_required_env_vars()

# ВАЖНО: Используем Bot Token для App, App Token для Socket Mode
app = App(token=Config.SLACK_BOT_TOKEN)

def generate_message(day_override: Optional[str] = None) -> str:
    """Generate message for debug mode."""
    try:
        message = generate_message_from_redis(day_override=day_override, debug_mode=True)
        if "_Нет задач на сегодня_" in message:
            logger.warning("Tasks not found in Redis, using fallback logic")
        return message
    except Exception as e:
        logger.error(f"Error generating debug message: {e}")
        return "❌ Error generating debug message"

@app.event("app_mention")
def handle_task_update(event: Dict[str, Any], say, client) -> None:
    """Handle app mentions for task completion and debug commands."""
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

                # Используем ТОЛЬКО client из контекста Bolt
                response = client.chat_postMessage(
                    channel=Config.SLACK_CHANNEL_ID,
                    text=message
                )
                set_thread_ts(response["ts"], debug_mode=True)

                # Используем say для ответа в том же треде
                say(f"<@{user}> sent task message (debug mode)")
                logger.info(f"Debug message sent by user {user}")
                return

            except Exception as e:
                logger.error(f"Error handling debug command: {e}")
                # Простой ответ без thread_ts при ошибке
                say(f"<@{user}> ❌ Error sending debug message")
                return

        # Определяем debug режим
        debug_mode = False
        debug_thread_ts = get_thread_ts(debug_mode=True)

        if thread_ts == debug_thread_ts:
            debug_mode = True
            logger.info("🔧 DEBUG MODE: используем debug_routine_state")

        task = find_task_in_text(text)
        if task:
            ok, msg = record_task(task, user, debug_mode=debug_mode)
            if not ok:
                say(f"<@{user}> {msg}")
                return

            # Проверяем дедлайны
            task_deadlines = get_task_deadlines()
            deadline = task_deadlines.get(task)

            if deadline:
                deadline_dt = riga.localize(datetime.datetime.combine(ts.date(), deadline))
                logger.info(f"⏱️ Сейчас: {ts.strftime('%H:%M:%S')} | Дедлайн для {task}: {deadline_dt.strftime('%H:%M:%S')}")

                if ts > deadline_dt:
                    prefix = "🔧 DEBUG: " if debug_mode else ""
                    say(f"{prefix}<@{user}> {task} было сделано поздно!")
                else:
                    # Добавляем реакцию
                    client.reactions_add(
                        channel=event["channel"],
                        timestamp=event["ts"],
                        name="white_check_mark"
                    )
            else:
                # Задачи без дедлайна - просто галочка
                client.reactions_add(
                    channel=event["channel"],
                    timestamp=event["ts"],
                    name="white_check_mark"
                )
        else:
            prefix = "🔧 DEBUG: " if debug_mode else ""
            say(f"{prefix}<@{user}> я не понял, о какой задаче речь 🤔. Напиши, например: `@bot LPB done`")

    except Exception as e:
        logger.error(f"Error in handle_task_update: {e}")
        # Максимально простой ответ при критической ошибке
        try:
            say(f"<@{user}> ❌ Произошла ошибка при обработке команды")
        except:
            logger.error("Failed to send error message to user")

if __name__ == "__main__":
    # ВАЖНО: App Token для Socket Mode Handler
    SocketModeHandler(app, Config.SLACK_APP_TOKEN).start()
