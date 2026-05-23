# Nextwave AI — Discord Attendance Bot

Tracks member activity on a Discord server and logs attendance to SQLite and Google Sheets.

## Team

- **Anush Tamang** — bot core, batch sync, message tracking, admin command
- **Animesh** — Google Sheets integration, daily summary

## Setup

1. Python 3.10+
2. `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and fill in values
4. Google Cloud: enable Sheets API, create service account, download `credentials.json`, share the sheet with the service account email
5. Invite bot to server with intents: **Server Members Intent**, **Message Content Intent**

## Run

```bash
python bot.py
```

## Commands

- `!attendance today` — (Admin only) shows today's present / not seen list
