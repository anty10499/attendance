"""
Discord Attendance Bot — Nextwave AI
Anush: core bot, batch sync, message tracking, !attendance, logging
"""
import logging
import os
import sqlite3
from datetime import date, datetime
from logging.handlers import RotatingFileHandler

import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
DB_PATH = os.getenv("DB_PATH", "attendance.db")
SUMMARY_CHANNEL_ID = os.getenv("SUMMARY_CHANNEL_ID")

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.presences = True

bot = commands.Bot(command_prefix="!", intents=intents)

# In-memory set of (discord_id, date) already marked present today
_present_today: set[tuple[str, str]] = set()


def setup_logging() -> None:
    handler = RotatingFileHandler("bot.log", maxBytes=5_000_000, backupCount=3)
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] [%(levelname)s] %(message)s",
        handlers=[handler, logging.StreamHandler()],
    )


def init_db() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS attendance_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            member_id TEXT NOT NULL,
            member_name TEXT NOT NULL,
            discord_id TEXT NOT NULL,
            status TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            date TEXT NOT NULL,
            synced INTEGER DEFAULT 0
        )
        """
    )
    conn.commit()
    conn.close()


def log_attendance(member: discord.Member, status: str = "PRESENT") -> None:
    if member.bot:
        return
    today = date.today().strftime("%d/%m/%Y")
    key = (str(member.id), today)
    if key in _present_today:
        return
    ts = datetime.now().strftime("%H:%M:%S")
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        INSERT INTO attendance_log (member_id, member_name, discord_id, status, timestamp, date, synced)
        VALUES (?, ?, ?, ?, ?, ?, 0)
        """,
        (str(member.id), member.display_name, str(member.id), status, ts, today),
    )
    conn.commit()
    conn.close()
    _present_today.add(key)
    logging.info("Logged %s as %s on %s", member.display_name, status, today)


def load_today_state() -> None:
    today = date.today().strftime("%d/%m/%Y")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT discord_id FROM attendance_log WHERE date = ? AND status = 'PRESENT'",
        (today,),
    )
    for (did,) in cur.fetchall():
        _present_today.add((did, today))
    conn.close()
    logging.info("Restored %s present records for today", len(_present_today))


def run_batch_sync() -> None:
    try:
        from spreadsheet import batch_sync_from_sqlite

        n = batch_sync_from_sqlite(DB_PATH)
        if n:
            logging.info("Synced %s rows to Google Sheets", n)
    except Exception as exc:
        logging.warning("Batch sync skipped: %s", exc)


@bot.event
async def on_ready():
    setup_logging()
    init_db()
    load_today_state()
    logging.info("Bot connected as %s", bot.user)
    # Schedule batch sync every 5 minutes
    import asyncio

    async def sync_loop():
        while True:
            await asyncio.sleep(300)
            run_batch_sync()

    bot.loop.create_task(sync_loop())


@bot.event
async def on_member_join(member: discord.Member):
    log_attendance(member, "JOINED")


@bot.event
async def on_presence_update(before: discord.Member, after: discord.Member):
    if after.bot:
        return
    if after.status != discord.Status.offline:
        log_attendance(after)


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        await bot.process_commands(message)
        return
    if isinstance(message.author, discord.Member):
        log_attendance(message.author)
    await bot.process_commands(message)


@bot.command(name="attendance")
@commands.has_permissions(administrator=True)
async def attendance_today(ctx: commands.Context):
    """Admin: show today's attendance summary."""
    today = date.today().strftime("%d/%m/%Y")
    guild = ctx.guild
    if not guild:
        await ctx.send("Guild not found.")
        return
    humans = [m for m in guild.members if not m.bot]
    present = []
    absent = []
    for m in humans:
        if (str(m.id), today) in _present_today:
            present.append(m.display_name)
        else:
            absent.append(m.display_name)
    msg = (
        f"**Attendance for {today}**\n"
        f"**Present ({len(present)}):** {', '.join(present) or 'None'}\n"
        f"**Not seen yet ({len(absent)}):** {', '.join(absent) or 'None'}"
    )
    await ctx.send(msg)


async def post_daily_summary():
    if not SUMMARY_CHANNEL_ID:
        return
    channel = bot.get_channel(int(SUMMARY_CHANNEL_ID))
    if not channel:
        return
    today = date.today().strftime("%d/%m/%Y")
    guild = channel.guild
    humans = [m for m in guild.members if not m.bot]
    present = [m.display_name for m in humans if (str(m.id), today) in _present_today]
    absent = [m.display_name for m in humans if (str(m.id), today) not in _present_today]
    await channel.send(
        f"**Attendance Summary — {today}**\n"
        f"Active today: {', '.join(present) or 'None'}\n"
        f"Not seen today: {', '.join(absent) or 'None'}"
    )


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("Set DISCORD_TOKEN in .env")
    bot.run(TOKEN, reconnect=True)
