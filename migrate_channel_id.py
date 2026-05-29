#!/usr/bin/env -S uv run --script

# /// script
# dependencies = [
#    "python-dotenv>=1.0.0",
# ]
# ///

"""Migration: add slack_channel_id column to tenants table."""

import sqlite3

from dotenv import load_dotenv

from db import DATABASE_PATH

load_dotenv()


def migrate():
    conn = sqlite3.connect(DATABASE_PATH)
    try:
        cols = [row[1] for row in conn.execute("PRAGMA table_info(tenants)").fetchall()]
        if "slack_channel_id" in cols:
            print("Column slack_channel_id already exists, skipping.")
            return
        conn.execute("ALTER TABLE tenants ADD COLUMN slack_channel_id VARCHAR(50)")
        conn.commit()
        print("Added slack_channel_id column to tenants table.")
        print()
        print("WARNING: You must set slack_channel_id for each tenant:")
        print('  sqlite3 user.db "UPDATE tenants SET slack_channel_id = \'CXXXXXXX\' WHERE name = \'Team Name\'"')
        print()
        print("Notifications will be skipped for tenants without a channel ID configured.")
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
