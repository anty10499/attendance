"""Google Sheets integration — Animesh / shared module."""
import os
from datetime import date
from typing import Optional

import gspread
from google.oauth2.service_account import Credentials

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
HEADERS = ["Date", "Member Name", "Discord ID", "Status", "Timestamp"]


def get_worksheet():
    creds_file = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")
    sheet_id = os.getenv("GOOGLE_SHEET_ID")
    if not sheet_id:
        raise ValueError("GOOGLE_SHEET_ID missing in .env")
    credentials = Credentials.from_service_account_file(creds_file, scopes=SCOPES)
    client = gspread.authorize(credentials)
    return client.open_by_key(sheet_id).sheet1


def ensure_headers(ws) -> None:
    row1 = ws.row_values(1)
    if row1 != HEADERS:
        ws.update("A1:E1", [HEADERS])


def upsert_daily_row(
    member_name: str,
    discord_id: str,
    status: str,
    timestamp: str,
    day: Optional[str] = None,
) -> None:
    """One row per member per day — update if exists."""
    ws = get_worksheet()
    ensure_headers(ws)
    day = day or date.today().strftime("%d/%m/%Y")
    records = ws.get_all_records()
    target_row = None
    for idx, rec in enumerate(records, start=2):
        if str(rec.get("Discord ID")) == str(discord_id) and rec.get("Date") == day:
            target_row = idx
            break
    row = [day, member_name, discord_id, status, timestamp]
    if target_row:
        ws.update(f"A{target_row}:E{target_row}", [row])
    else:
        ws.append_row(row, value_input_option="USER_ENTERED")


def batch_sync_from_sqlite(db_path: str = "attendance.db") -> int:
    """Push unsynced SQLite rows to Sheets (called every 5 minutes)."""
    import sqlite3

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, member_name, discord_id, status, timestamp, date
        FROM attendance_log WHERE synced = 0
        """
    )
    rows = cur.fetchall()
    count = 0
    for row_id, name, did, status, ts, day in rows:
        try:
            upsert_daily_row(name, did, status, ts, day)
            cur.execute("UPDATE attendance_log SET synced = 1 WHERE id = ?", (row_id,))
            count += 1
        except Exception as exc:
            print(f"[Sheets] sync failed for {did}: {exc}")
    conn.commit()
    conn.close()
    return count
