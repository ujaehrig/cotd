#!/usr/bin/env -S uv run --script

# /// script
# dependencies = [
#    "python-dotenv>=1.0.0",
# ]
# ///

"""
Migration: Remove authentication columns from user table.

The Flask web UI has been removed. These columns are no longer used:
- password_hash
- password_reset_required
- password_reset_token
- password_reset_expires

Requires SQLite 3.35.0+ (ALTER TABLE DROP COLUMN support).
"""

import os
import sqlite3
import logging
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

DATABASE_PATH = Path(os.getenv("DB_PATH", Path(__file__).parent / "user.db"))

COLUMNS_TO_DROP = [
    "password_hash",
    "password_reset_required",
    "password_reset_token",
    "password_reset_expires",
]


def main():
    if not DATABASE_PATH.exists():
        logging.error(f"Database not found: {DATABASE_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # Get existing columns
    cursor.execute("PRAGMA table_info(user)")
    existing = {row[1] for row in cursor.fetchall()}

    dropped = []
    for col in COLUMNS_TO_DROP:
        if col in existing:
            logging.info(f"Dropping column: {col}")
            cursor.execute(f"ALTER TABLE user DROP COLUMN {col}")
            dropped.append(col)
        else:
            logging.info(f"Column already absent: {col}")

    conn.commit()
    conn.close()

    if dropped:
        logging.info(f"Migration complete. Dropped {len(dropped)} column(s): {', '.join(dropped)}")
    else:
        logging.info("Nothing to migrate — auth columns already removed.")


if __name__ == "__main__":
    main()
