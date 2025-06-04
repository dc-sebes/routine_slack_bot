import os
import datetime
import pytz
from slack_sdk import WebClient
from redis_bot import get_tasks_for_day, get_completed_tasks, get_thread_ts

client = WebClient(token=os.environ.get("SLACK_BOT_TOKEN"))
CHANNEL_ID = os.environ.get("SLACK_CHANNEL_ID")

# Захардкоженная команда для тегинга
TEAM_MENTION = "<!subteam^S07BD1P55GT|@sup>"

def get_incomplete_tasks():
    #Получить невыполненные задачи с учетом времени напоминания
    riga = pytz.timezone("Europe/Riga")
    today = datetime.datetime.now(riga)
    day_name = today.strftime('%A')
    current_hour = today.hour

    # Получаем все задачи на сегодня
    all_tasks = get_tasks_for_day(day_name)

    # Получаем выполненные задачи из slack_routine_state
    completed_tasks = get_completed_tasks(debug_mode=False)
    completed_names = [name.upper() for name in completed_tasks.keys()]

    # Фильтруем невыполненные задачи
    incomplete_tasks = []
    overdue_tasks = []

    for task in all_tasks:
        task_name_upper = task.get("name", "").upper()

        # Пропускаем выполненные задачи
        if task_name_upper in completed_names:
            continue

        deadline_str = task.get("deadline", "")

        # Если есть дедлайн, проверяем логику по времени
        if deadline_str:
            try:
                hour, minute = map(int, deadline_str.split(":"))
                deadline_hour = hour

                # В 13:00 не показываем задачи с дедлайном 16:00+
                if current_hour == 13 and deadline_hour >= 16:
                    continue

                # Проверяем, просрочена ли задача
                current_time = today.time()
                deadline_time = datetime.time(hour=hour, minute=minute)

                if current_time > deadline_time:
                    overdue_tasks.append(task)
                else:
                    incomplete_tasks.append(task)

            except ValueError:
                # Если не удалось распарсить время, добавляем в обычные
                incomplete_tasks.append(task)
        else:
            # Задачи без дедлайна всегда показываем
            incomplete_tasks.append(task)

    return incomplete_tasks, overdue_tasks

def format_reminder_message():
    #Форматировать сообщение-напоминание
    riga = pytz.timezone("Europe/Riga")
    today = datetime.datetime.now(riga)
    current_time = today.strftime('%H:%M')
    date_str = today.strftime('%d %B (%A)')

    incomplete_tasks, overdue_tasks = get_incomplete_tasks()

    # Если нет задач для напоминания
    if not incomplete_tasks and not overdue_tasks:
        return None

    message_parts = []

    # Заголовок
    header = f"⏰ Напоминание в {current_time} - {date_str}"
    message_parts.append(header)

    # Просроченные задачи
    if overdue_tasks:
        message_parts.append("\n🚨 *ПРОСРОЧЕННЫЕ ЗАДАЧИ:*")
        for task in overdue_tasks:
            name = task.get("name", "")
            deadline = task.get("deadline", "")
            line = f"• *{name}* (дедлайн был в {deadline})"
            message_parts.append(line)

    # Остальные невыполненные задачи
    if incomplete_tasks:
        message_parts.append("\n📋 *НЕВЫПОЛНЕННЫЕ ЗАДАЧИ:*")
        for task in incomplete_tasks:
            name = task.get("name", "")
            deadline = task.get("deadline", "")
            line = f"• *{name}*"
            if deadline:
                line += f" (до {deadline})"
            message_parts.append(line)

    # Добавляем тег команды в конец
    message_parts.append(f"\n{TEAM_MENTION}")

    return "\n".join(message_parts)

def send_reminder():
    #Отправить напоминание в Slack
    message = format_reminder_message()

    if not message:
        print("ℹ️ Нет задач для напоминания")
        return False

    # Получаем thread_ts текущего дня
    thread_ts = get_thread_ts(debug_mode=False)

    try:
        if thread_ts:
            # Отправляем в тред с ежедневными задачами
            response = client.chat_postMessage(
                channel=CHANNEL_ID,
                text=message,
                thread_ts=thread_ts
            )
            print(f"✅ Напоминание отправлено в тред")
        else:
            # Если нет активного треда, отправляем отдельным сообщением
            response = client.chat_postMessage(
                channel=CHANNEL_ID,
                text=message
            )
            print(f"✅ Напоминание отправлено отдельным сообщением")

        return True

    except Exception as e:
        print(f"❌ Ошибка при отправке напоминания: {e}")
        return False

if __name__ == "__main__":
    # Проверяем рабочий день
    today = datetime.datetime.now()
    if today.weekday() < 5:  # только рабочие дни
        current_time = today.strftime('%H:%M')
        print(f"⏰ Запуск напоминалки в {current_time}")
        send_reminder()
    else:
        print("Сегодня выходной, напоминания не отправляются")
