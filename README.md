# Routine Slack Bot

A comprehensive Slack bot system for daily task tracking, completion monitoring, and automated reminders.

## Overview

This bot system helps teams manage daily routines by:
- Posting morning task lists to Slack channels
- Tracking task completion through @mentions
- Sending reminders for incomplete or overdue tasks
- Supporting debug mode for testing workflows

## Components

- **main_bot.py** - Interactive bot handling task completion via @mentions
- **cron_bot.py** - Daily cron job posting morning task lists
- **reminder_bot.py** - Automated reminder system for incomplete tasks
- **redis_bot.py** - Central data layer managing Redis storage

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Set environment variables:
   ```bash
   export SLACK_BOT_TOKEN="xoxb-..."
   export SLACK_APP_TOKEN="xapp-..."
   export SLACK_CHANNEL_ID="C..."
   export REDIS_URL="redis://..."
   ```

3. Run components:
   ```bash
   # Interactive bot
   python main_bot.py
   
   # Daily task poster (via cron)
   python cron_bot.py
   
   # Reminder system (via cron)
   python reminder_bot.py
   ```

## Usage

- Complete tasks: `@bot TaskName done`
- Debug mode: `@bot debug` or `@bot debug monday`
- Tasks are timezone-aware (Europe/Riga)
- Operates weekdays only (Monday-Friday)

## Data Storage

Tasks stored in Redis with structure supporting deadlines, day restrictions, and Asana integration.