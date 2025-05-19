import os
import json
import datetime
import redis

# Подключение к Redis по переменной окружения
redis_url = os.environ.get("REDIS_URL")
r = redis.Redis.from_url(redis_url)

REDIS_KEY = "slack_routine_state"

def load_state():
    data = r.get(REDIS_KEY)
    if data:
        return json.loads(data)
    return {}

def save_state(state):
    r.set(REDIS_KEY, json.dumps(state))

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
