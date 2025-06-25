import json
import datetime
import redis
import re
import logging
from typing import Dict, List, Optional, Tuple, Any
from config import Config

# Setup logging
logger = logging.getLogger(__name__)

# Redis connection with error handling
try:
    r = redis.Redis.from_url(Config.REDIS_URL)
    # Test connection
    r.ping()
    logger.info("Successfully connected to Redis")
except redis.ConnectionError as e:
    logger.error(f"Failed to connect to Redis: {e}")
    raise
except Exception as e:
    logger.error(f"Unexpected error connecting to Redis: {e}")
    raise

def load_state(debug_mode: bool = False) -> Dict[str, Any]:
    #Load routine state (normal or debug mode).
    try:
        key = Config.DEBUG_ROUTINE_STATE if debug_mode else Config.SLACK_ROUTINE_STATE
        data = r.get(key)
        if data:
            return json.loads(data)
        return {}
    except (redis.RedisError, json.JSONDecodeError) as e:
        logger.error(f"Error loading state (debug_mode={debug_mode}): {e}")
        return {}

def save_state(state: Dict[str, Any], debug_mode: bool = False) -> bool:
    #Save routine state (normal or debug mode).
    try:
        key = Config.DEBUG_ROUTINE_STATE if debug_mode else Config.SLACK_ROUTINE_STATE
        r.set(key, json.dumps(state))
        logger.debug(f"State saved successfully (debug_mode={debug_mode})")
        return True
    except (redis.RedisError, json.JSONEncodeError) as e:
        logger.error(f"Error saving state (debug_mode={debug_mode}): {e}")
        return False

def load_task_base() -> Dict[str, Any]:
    #Load task base from Redis.
    try:
        data = r.get(Config.TASK_BASE)
        if data:
            return json.loads(data)
        logger.warning("Task base is empty or not found")
        return {}
    except (redis.RedisError, json.JSONDecodeError) as e:
        logger.error(f"Error loading task base: {e}")
        return {}

def save_task_base(task_base: Dict[str, Any]) -> bool:
    #Save task base to Redis.
    try:
        r.set(Config.TASK_BASE, json.dumps(task_base))
        logger.debug("Task base saved successfully")
        return True
    except (redis.RedisError, json.JSONEncodeError) as e:
        logger.error(f"Error saving task base: {e}")
        return False

def set_thread_ts(thread_ts, debug_mode=False):
    #Установить thread_ts для нового дня
    state = load_state(debug_mode)
    state["date"] = datetime.date.today().isoformat()
    state["thread_ts"] = thread_ts
    state["completed"] = {}
    save_state(state, debug_mode)

def get_thread_ts(debug_mode=False):
    #Получить текущий thread_ts
    state = load_state(debug_mode)
    return state.get("thread_ts")

def record_task(task, user, debug_mode=False):
    #Записать выполненную задачу
    state = load_state(debug_mode)
    today = datetime.date.today().isoformat()

    if state.get("date") != today:
        return False, "Старое состояние — новое утро, нет активного треда."

    if "completed" not in state:
        state["completed"] = {}

    if task in state["completed"]:
        return False, "Эта задача уже была отмечена ранее."

    now = datetime.datetime.now().strftime("%H:%M")
    state["completed"][task] = {"user": user, "time": now}
    save_state(state, debug_mode)
    return True, None

def get_completed_tasks(debug_mode=False):
    #Получить список выполненных задач
    state = load_state(debug_mode)
    return state.get("completed", {})

def get_tasks_for_day(day_name):
    #Получить задачи для конкретного дня недели из task_base
    task_base = load_task_base()

    if not task_base:
        return []

    tasks = []
    for task_id, task_data in task_base.items():
        # Проверяем, выполняется ли задача в этот день
        task_days = task_data.get("days", "all")
        if task_days == "all" or day_name in task_days:
            # Добавляем ID задачи к данным
            task_with_id = task_data.copy()
            task_with_id["id"] = task_id
            tasks.append(task_with_id)

    return tasks

    # Сортируем по времени дедлайна
    tasks.sort(key=lambda x: x.get("deadline", "23:59"))
    return tasks

def format_task_line(task):
    #Форматировать строку задачи для Slack
    name = task.get("name", "")
    deadline = task.get("deadline", "")
    asana_url = task.get("asana_url", "")
    comments = task.get("comments", "")

    # Базовая строка с чекбоксом и эмодзи времени
    if deadline:
        task_line = f"- [ ] *{name}* до {deadline}"
    else:
        task_line = f"- [ ] *{name}*"

    # Добавляем ссылку на Asana в Slack-специфичном формате
    if asana_url:
        task_line += f" • <{asana_url}|Asana>"

    # Добавляем комментарии на новой строке с отступом
    if comments:
        task_line += f"\n    _{comments}_"

    return task_line

def generate_message_from_redis(day_override=None, debug_mode=False):
    #Генерировать сообщение для Slack на основе данных из Redis с группировкой и сотрудниками
    today = datetime.datetime.now()

    if day_override:
        day_name = day_override.capitalize()
        date_str = today.strftime('%d %B') + f" ({day_name})"
        # Для day_override используем текущую дату в формате dd/mm
        current_date = today.strftime('%d/%m')
    else:
        day_name = today.strftime('%A')
        date_str = today.strftime('%d %B (%A)')
        current_date = today.strftime('%d/%m')

    # Получаем задачи для дня
    tasks = get_tasks_for_day(day_name)

    # Формируем заголовок
    debug_prefix = "🔧 DEBUG: " if debug_mode else ""
    header = f"{debug_prefix}🎓 Routine tasks for *{date_str}*"

    # Если нет задач
    if not tasks:
        return header + "\n\n_Нет задач на сегодня_"

    # Группируем задачи
    grouped_tasks = group_tasks_by_period(tasks)

    message_parts = [header]

    # Сначала показываем задачи без группы
    if grouped_tasks["ungrouped"]:
        message_parts.append("")  # Пустая строка для отступа
        for task in grouped_tasks["ungrouped"]:
            message_parts.append(format_task_line(task))

    # Потом утренние задачи
    if grouped_tasks["morning"]:
        # Получаем сотрудников для утренней смены
        morning_employees = get_employees_for_date_and_period(current_date, "morning")
        employees_mention = format_employees_mention(morning_employees)

        if employees_mention:
            message_parts.append(f"\n*Утро*:\n{employees_mention}")
        else:
            message_parts.append("\n*Утро*:")

        for task in grouped_tasks["morning"]:
            message_parts.append(format_task_line(task))

    # Потом вечерние задачи
    if grouped_tasks["evening"]:
        # Получаем сотрудников для вечерней смены
        evening_employees = get_employees_for_date_and_period(current_date, "evening")
        employees_mention = format_employees_mention(evening_employees)

        if employees_mention:
            message_parts.append(f"\n*Вечер* _(делается после 15:00)_:\n{employees_mention}")
        else:
            message_parts.append("\n*Вечер*:")

        for task in grouped_tasks["evening"]:
            message_parts.append(format_task_line(task))

    return "\n".join(message_parts)

def get_task_deadlines():
    #Получить дедлайны задач для проверки времени выполнения
    task_base = load_task_base()
    deadlines = {}

    for task_id, task_data in task_base.items():
        deadline_str = task_data.get("deadline", "")
        if deadline_str:
            try:
                # Преобразуем строку "HH:MM" в объект времени
                hour, minute = map(int, deadline_str.split(":"))
                deadlines[task_data.get("name", "").upper()] = datetime.time(hour=hour, minute=minute)
            except ValueError:
                # Если не удалось распарсить время, пропускаем
                continue
        else:
            # Задачи без дедлайна
            deadlines[task_data.get("name", "").upper()] = None

    return deadlines

def get_task_names():
    #Получить все названия задач для регулярного выражения
    task_base = load_task_base()

    if not task_base:
        print("Скорее всего, Redis пуст")

    names = []
    for task_id, task_data in task_base.items():
        name = task_data.get("name", "")
        if name:
            names.append(name)

    return names

def build_task_regex():
    #Построить регулярное выражение для поиска задач
    task_names = get_task_names()

    # Экранируем специальные символы в названиях (например, дефисы)
    escaped_names = [re.escape(name) for name in task_names]

    # Создаем паттерн: (LPB|KYC-1|Проверка KYC-2|Statements - выгрузки).*done
    pattern = r"(?i)(" + "|".join(escaped_names) + r").*done"
    return pattern

def find_task_in_text(text):
    #Найти упоминание задачи в тексте
    pattern = build_task_regex()
    match = re.search(pattern, text)

    if match:
        # Возвращаем найденное название задачи
        found_name = match.group(1)

        # Нормализуем название для поиска в deadlines
        # (приводим к тому виду, который используется в get_task_deadline)
        normalized_name = found_name.upper()

        return normalized_name

    return None

def group_tasks_by_period(tasks):
    #Группировать задачи по периодам (утро/вечер)
    groups = {
        "ungrouped": [],  # Задачи без группы
        "morning": [],    # Утренние задачи
        "evening": []     # Вечерние задачи
    }

    for task in tasks:
        period = task.get("period", "")
        if period == "morning":
            groups["morning"].append(task)
        elif period == "evening":
            groups["evening"].append(task)
        else:
            groups["ungrouped"].append(task)

    # Сортируем задачи в каждой группе по времени дедлайна
    for group_name in groups:
        groups[group_name].sort(key=lambda x: x.get("deadline", "23:59"))

    return groups

#Employees

def load_employees() -> Dict[str, Any]:
    #Загрузить данные сотрудников из Redis
    try:
        data = r.get(Config.EMPLOYEES)
        if data:
            return json.loads(data)
        logger.warning("Employee data is empty or not found")
        return {}
    except (redis.RedisError, json.JSONDecodeError) as e:
        logger.error(f"Error loading employees: {e}")
        return {}

def save_employees(employees: Dict[str, Any]) -> bool:
    #Сохранить данные сотрудников в Redis
    try:
        r.set(Config.EMPLOYEES, json.dumps(employees))
        logger.debug("Employees data saved successfully")
        return True
    except (redis.RedisError, json.JSONEncodeError) as e:
        logger.error(f"Error saving employees: {e}")
        return False

def get_employees_for_date_and_period(date_str: str, period: str) -> List[Dict[str, str]]:
    #Получить сотрудников, работающих в указанную дату и период
    employees = load_employees()
    working_employees = []

    for emp_id, emp_data in employees.items():
        name = emp_data.get("name", "")
        slack_id = emp_data.get("slack_id", "")

        # Получаем даты работы для указанного периода
        if period == "morning":
            work_dates = emp_data.get("morning_dates", [])
        elif period == "evening":
            work_dates = emp_data.get("evening_dates", [])
        else:
            continue

        # Проверяем, работает ли сотрудник в эту дату
        if date_str in work_dates:
            working_employees.append({
                "name": name,
                "slack_id": slack_id,
                "employee_id": emp_id
            })

    return working_employees

def format_employees_mention(employees: List[Dict[str, str]]) -> str:
    #Форматировать упоминания сотрудников для Slack
    if not employees:
        return ""

    mentions = []
    for emp in employees:
        slack_id = emp.get("slack_id", "")
        if slack_id:
            mentions.append(f"<@{slack_id}>")
        else:
            # Если нет slack_id, используем имя
            mentions.append(emp.get("name", "Unknown"))

    return "[" + " + ".join(mentions) + "]"

def load_task_assignments() -> Dict[str, str]:
    #Загрузить назначения пользователей на задачи из employees
    try:
        employees_data = load_employees()
        # Назначения хранятся в специальном разделе employees
        return employees_data.get("task_assignments", {})
    except Exception as e:
        logger.error(f"Error loading task assignments: {e}")
        return {}

def save_task_assignments(assignments: Dict[str, str]) -> bool:
    #Сохранить назначения пользователей на задачи в employees
    try:
        employees_data = load_employees()
        # Сохраняем назначения в специальном разделе
        employees_data["task_assignments"] = assignments
        return save_employees(employees_data)
    except Exception as e:
        logger.error(f"Error saving task assignments: {e}")
        return False

def set_task_assignment(task_name: str, user_id: str = None) -> bool:
    #Назначить или снять пользователя с задачи
    assignments = load_task_assignments()

    # Нормализуем название задачи (приводим к верхнему регистру)
    task_key = task_name.upper()

    if user_id:
        # Назначаем пользователя
        assignments[task_key] = user_id
        logger.info(f"User {user_id} assigned to task {task_name}")
    else:
        # Снимаем назначение
        if task_key in assignments:
            del assignments[task_key]
            logger.info(f"Assignment removed from task {task_name}")

    return save_task_assignments(assignments)

def get_task_assignment(task_name: str) -> str:
    #Получить назначенного пользователя для задачи
    assignments = load_task_assignments()
    task_key = task_name.upper()
    return assignments.get(task_key, "")

def find_task_by_pattern(pattern: str) -> str:
    #Найти задачу по паттерну (например, fin-duty)
    task_base = load_task_base()

    pattern_lower = pattern.lower()
    for task_id, task_data in task_base.items():
        task_name = task_data.get("name", "").lower()
        if pattern_lower in task_name:
            return task_data.get("name", "")

    return ""
