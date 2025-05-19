import os
import datetime
from slack_sdk import WebClient
from task_tracker import set_thread_ts

client = WebClient(token=os.environ.get("SLACK_BOT_TOKEN"))
CHANNEL_ID = os.environ.get("SLACK_CHANNEL_ID")

def generate_message():
    today = datetime.datetime.now()
    day_name = today.strftime('%A')
    date_str = today.strftime('%d %B (%A)')

    if day_name == "Monday":
        tasks = [
            "- [ ] Statements - выгрузки",
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

    header = f"\ud83c\udf93 Routine tasks for *{date_str}*"
    return header + "\n\n" + "\n".join(tasks)

if __name__ == "__main__":
    today = datetime.datetime.today()
    if today.weekday() < 5:  # 0–4: Monday–Friday
        message = generate_message()
        client.chat_postMessage(channel=CHANNEL_ID, text=message)
        response = client.chat_postMessage(channel=CHANNEL_ID, text=message)
        set_thread_ts(response["ts"])
