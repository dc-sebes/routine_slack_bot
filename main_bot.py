import pytz
import datetime
from typing import Dict, Any, Optional
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from config import Config
from redis_bot import (
    set_thread_ts, record_task, get_thread_ts,
    generate_message_from_redis, get_task_deadlines, find_task_in_text,
    set_task_assignment, find_task_by_pattern  # Новые функции
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

                # Создаем новое сообщение с задачами
                response = client.chat_postMessage(
                    channel=Config.SLACK_CHANNEL_ID,
                    text=message
                )
                set_thread_ts(response["ts"], debug_mode=True)

                say(
                    text=f"<@{user}> sent task message (debug mode)",
                    thread_ts=response["ts"]  # В треде нового сообщения
                )
                logger.info(f"Debug message sent by user {user}")
                return

            except Exception as e:
                logger.error(f"Error handling debug command: {e}")
                # Отвечаем в исходном треде
                say(
                    text=f"<@{user}> ❌ Error sending debug message",
                    thread_ts=thread_ts
                )
                return

        # Определяем debug режим по thread_ts
        debug_mode = False
        production_thread_ts = get_thread_ts(debug_mode=False)
        debug_thread_ts = get_thread_ts(debug_mode=True)

        if thread_ts == debug_thread_ts:
            debug_mode = True
            logger.info("🔧 DEBUG MODE: используем debug_routine_state")
        elif thread_ts == production_thread_ts:
            debug_mode = False
            logger.info("📋 PRODUCTION MODE: используем slack_routine_state")
        else:
            # Если не в известном треде, используем production по умолчанию
            debug_mode = False
            # Используем production thread_ts для ответа
            if production_thread_ts:
                thread_ts = production_thread_ts
            logger.info("📋 DEFAULT MODE: используем slack_routine_state")

        task = find_task_in_text(text)
        if task:
            ok, msg = record_task(task, user, debug_mode=debug_mode)
            if not ok:
                say(
                    text=f"<@{user}> {msg}",
                    thread_ts=thread_ts
                )
                return

            # Проверяем дедлайны
            task_deadlines = get_task_deadlines()
            deadline = task_deadlines.get(task)

            if deadline:
                deadline_dt = riga.localize(datetime.datetime.combine(ts.date(), deadline))
                logger.info(f"⏱️ Сейчас: {ts.strftime('%H:%M:%S')} | Дедлайн для {task}: {deadline_dt.strftime('%H:%M:%S')}")

                if ts > deadline_dt:
                    prefix = "🔧 DEBUG: " if debug_mode else ""
                    say(
                        text=f"{prefix}<@{user}> {task} было сделано поздно!",
                        thread_ts=thread_ts
                    )
                else:
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
            say(
                text=f"{prefix}<@{user}> я не понял, о какой задаче речь 🤔. Напиши, например: `@bot LPB done`",
                thread_ts=thread_ts
            )

    except Exception as e:
        logger.error(f"Error in handle_task_update: {e}")
        try:
            say(
                text=f"<@{user}> ❌ Произошла ошибка при обработке команды",
                thread_ts=thread_ts
            )
        except:
            logger.error("Failed to send error message to user")

@app.command("/set-fin-duty")
def handle_set_fin_duty(ack, command, say):
    #Обработчик команды /set-fin-duty
    ack()

    try:
        user_id = command.get("user_id")
        text = command.get("text", "").strip()

        # Ищем задачу, содержащую "fin-duty" или "fin duty"
        task_name = find_task_by_pattern("fin")

        if not task_name:
            say("❌ Задача с 'fin' в названии не найдена в системе")
            return

        # Парсим команду
        if not text:
            # Пустая команда - снимаем назначение
            if set_task_assignment(task_name):
                say(f"✅ Назначение с задачи *{task_name}* снято")
            else:
                say("❌ Ошибка при снятии назначения")
            return

        # Извлекаем user ID из упоминания (@UXXXXXXX)
        import re
        user_mention_match = re.search(r'<@([UW][A-Z0-9]+)>', text)

        if user_mention_match:
            mentioned_user_id = user_mention_match.group(1)

            if set_task_assignment(task_name, mentioned_user_id):
                say(f"✅ Пользователь <@{mentioned_user_id}> назначен на задачу *{task_name}*")
            else:
                say("❌ Ошибка при назначении пользователя")
        else:
            say("❌ Не удалось найти упоминание пользователя. Используйте: `/set-fin-duty @username`")

    except Exception as e:
        logger.error(f"Error in handle_set_fin_duty: {e}")
        say("❌ Произошла ошибка при обработке команды")

if __name__ == "__main__":
    SocketModeHandler(app, Config.SLACK_APP_TOKEN).start()
