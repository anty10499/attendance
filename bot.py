"""Use this file as bot.py for feature/bot-base PR only (no Sheets yet)."""
import os
import sqlite3
from datetime import date, datetime

import discord
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
DB_PATH = "attendance.db"

intents = discord.Intents.default()
intents.members = True
intents.presences = True
client = discord.Client(intents=intents)


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS attendance_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            member_id TEXT, member_name TEXT, discord_id TEXT,
            status TEXT, timestamp TEXT, date TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def log_member(member: discord.Member, status: str):
    if member.bot:
        return
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO attendance_log (member_id, member_name, discord_id, status, timestamp, date) VALUES (?,?,?,?,?,?)",
        (str(member.id), member.display_name, str(member.id), status,
         datetime.now().strftime("%H:%M:%S"), date.today().strftime("%d/%m/%Y")),
    )
    conn.commit()
    conn.close()


@client.event
async def on_ready():
    init_db()
    print(f"Bot ready: {client.user}")


@client.event
async def on_member_join(member):
    log_member(member, "JOINED")


@client.event
async def on_presence_update(before, after):
    if after.bot:
        return
    if after.status != discord.Status.offline:
        log_member(after, "PRESENT")


if __name__ == "__main__":
    client.run(TOKEN)
