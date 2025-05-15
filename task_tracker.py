import os
import json
import datetime

STATE_FILE = "/tmp/slack_routine_state.json"

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

def set_thread_ts(thread_ts):
    state = load_state()
    state["date"] = datetime.date.today().isoformat()
    state["thread_ts"] = thread_ts
    state["completed"] = {}
    save_state(state)

def get_thread_ts():
    state = load_state()
    return state.get("thread_ts")

def record_task(task, user):
    state = load_state()
    today = datetime.date.today().isoformat()

    if state.get("date") != today:
        return False, "Старое состояние — новое утро, нет активного треда."

    if "completed" not in state:
        state["completed"] = {}

    if task in state["completed"]:
        return False, "Эта задача уже была отмечена ранее."

    now = datetime.datetime.now().strftime("%H:%M")
    state["completed"][task] = {"user": user, "time": now}
    save_state(state)
    return True, None

def get_completed_tasks():
    state = load_state()
    return state.get("completed", {})
