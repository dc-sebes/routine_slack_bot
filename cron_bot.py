import os
import datetime
from slack_sdk import WebClient
from redis_bot import generate_message_from_redis, set_thread_ts

client = WebClient(token=os.environ.get("SLACK_BOT_TOKEN"))
CHANNEL_ID = os.environ.get("SLACK_CHANNEL_ID")

def generate_message():
    #Генерировать сообщение для Slack на основе данных из Redis
    message = generate_message_from_redis()

    if "_Нет задач на сегодня_" in message:
        print("⚠️ Задачи не найдены в Redis, используем старую логику")
        today = datetime.datetime.now()
        date_str = today.strftime('%d %B (%A)')

        empty_redis_message = [
            "No tasks found in Redis, check BD"
        ]

        header = f"🎓 Routine tasks for *{date_str}*"
        return header + "\n\n" + "\n".join(empty_redis_message)

    return message

if __name__ == "__main__":
    today = datetime.datetime.today()
    if today.weekday() < 5:  # 0–4: Monday–Friday
        try:
            message = generate_message()
            response = client.chat_postMessage(channel=CHANNEL_ID, text=message)
            set_thread_ts(response["ts"])
            print("✅ Сообщение отправлено в Slack")
        except Exception as e:
            print(f"❌ Ошибка при отправке сообщения: {e}")
    else:
        print("Сегодня выходной, задачи не отправляются")
