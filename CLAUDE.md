# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Environment Setup

Required environment variables:
- `SLACK_BOT_TOKEN` - Bot user OAuth token
- `SLACK_APP_TOKEN` - App-level token for Socket Mode  
- `SLACK_CHANNEL_ID` - Target channel for daily messages
- `REDIS_URL` - Redis connection string for task storage

Install dependencies:
```bash
pip install -r requirements.txt
```

## Running the System

**Main bot (interactive task tracking):**
```bash
python main_bot.py
```

**Daily cron job (sends morning task lists):**
```bash
python cron_bot.py
```

**Reminder system (checks for incomplete tasks):**
```bash
python reminder_bot.py
```

## Architecture Overview

### Data Flow
1. **Task Database**: Redis stores task definitions in `task_base` key with structure:
   ```json
   {
     "task_id": {
       "name": "Task Name",
       "deadline": "HH:MM", 
       "days": ["Monday", "Tuesday"] | "all",
       "asana_url": "optional",
       "comments": "optional"
     }
   }
   ```

2. **State Management**: Two separate states in Redis:
   - `slack_routine_state` - Production task completion tracking
   - `debug_routine_state` - Testing/debug mode tracking

3. **Daily Workflow**:
   - `cron_bot.py` posts morning task list from Redis task database
   - `main_bot.py` handles @mentions for task completion (`@bot TaskName done`)
   - `reminder_bot.py` sends alerts for incomplete/overdue tasks

### Key Components

**redis_bot.py** - Central data layer:
- `get_tasks_for_day(day_name)` - Retrieves tasks for specific weekday
- `record_task(task, user, debug_mode)` - Marks task complete with timestamp
- `generate_message_from_redis()` - Formats daily task list for Slack
- `find_task_in_text(text)` - Regex matching for task completion mentions

**main_bot.py** - Interactive bot:
- Handles @mentions with pattern matching for task completion
- Supports debug mode via `@bot debug` or `@bot debug monday`
- Validates task deadlines against Riga timezone
- Adds checkmark reactions for on-time completion, posts warnings for late tasks

**reminder_bot.py** - Notification system:
- Filters incomplete tasks based on current time and deadlines
- At 13:00, excludes tasks with 16:00+ deadlines from reminders
- Tags team with `<!subteam^S07BD1P55GT|@sup>` for overdue tasks

### Debug Mode
- Triggered by mentioning bot with "debug" keyword
- Uses separate Redis state (`debug_routine_state`) 
- Prefixes messages with "🔧 DEBUG:" to distinguish from production
- Allows testing task flows without affecting real tracking

### Timezone Handling
- Uses `Europe/Riga` timezone for all deadline calculations
- Deadline validation compares current time against task deadline times
- Cron jobs and reminders respect weekday-only operation (Monday-Friday)

## Task Management Patterns

When adding new task types, update the Redis `task_base` with appropriate:
- Day restrictions (`"days": ["Monday"]` vs `"days": "all"`)
- Deadline times for reminder logic
- Asana integration URLs for task context

The regex pattern in `find_task_in_text()` auto-builds from task names in Redis, so new tasks are automatically recognized for completion tracking.