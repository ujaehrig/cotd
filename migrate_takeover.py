#!/usr/bin/env -S uv run --script

# /// script
# dependencies = [
#    "python-dotenv>=1.0.0",
# ]
# ///

"""Migration: add takeover_secret column to tenants table."""

import sqlite3

from dotenv import load_dotenv

from db import DATABASE_PATH

load_dotenv()


def migrate():
    conn = sqlite3.connect(DATABASE_PATH)
    try:
        # Check if column already exists
        cols = [row[1] for row in conn.execute("PRAGMA table_info(tenants)").fetchall()]
        if "takeover_secret" in cols:
            print("Column takeover_secret already exists, skipping.")
            return
        conn.execute("ALTER TABLE tenants ADD COLUMN takeover_secret VARCHAR(200)")
        conn.commit()
        print("Added takeover_secret column to tenants table.")
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
