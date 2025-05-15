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

task_deadlines = {
    "LPB": datetime.time(hour=12),
    "KYC-1": datetime.time(hour=11),
    "KYC-2": datetime.time(hour=16),
}

@app.event("app_mention")
def handle_task_update(event, say):
    text = event.get("text", "")
    user = event.get("user")
    thread_ts = event.get("thread_ts") or event.get("ts")
    ts = datetime.datetime.now()

    match = re.search(r"(?i)(LPB|KYC-1|KYC-2).*done", text)
    if match:
        task = match.group(1).upper()
        deadline = task_deadlines.get(task)
        if deadline:
            deadline_dt = datetime.datetime.combine(ts.date(), deadline)
            if ts > deadline_dt:
                say(text=f"<@{user}> {task} было сделано поздно!", thread_ts=thread_ts)
            else:
                client.reactions_add(
                    channel=event["channel"],
                    timestamp=event["ts"],
                    name="white_check_mark"
                )
    else:
        say(text=f"<@{user}> я не понял, о какой задаче речь 🤔. Напиши, например: `@bot LPB done`", thread_ts=thread_ts)

if __name__ == "__main__":
    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()
