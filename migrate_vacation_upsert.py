#!/usr/bin/env -S uv run --script

# /// script
# dependencies = [
#    "python-dotenv>=1.0.0",
# ]
# ///

"""
Migration: Add UNIQUE constraint on (user_id, ical_event_uid) to vacation table.

Required for the upsert sync strategy introduced alongside this migration.
SQLite does not support ADD CONSTRAINT, so the table is recreated.
"""

import sqlite3
import logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def migrate_database(db_path: str | None = None) -> None:
    """Add UNIQUE(user_id, ical_event_uid) to vacation table."""
    if db_path is None:
        from db import DATABASE_PATH
        db_path = DATABASE_PATH

    logger.info(f"Starting vacation upsert migration for: {db_path}")

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = OFF")

    try:
        conn.executescript("""
            BEGIN;

            CREATE TABLE vacation_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                start_date DATE NOT NULL,
                end_date DATE NOT NULL,
                source VARCHAR(20) DEFAULT 'manual',
                last_synced TIMESTAMP,
                ical_event_uid VARCHAR(200),
                FOREIGN KEY (user_id) REFERENCES user(id),
                UNIQUE (user_id, ical_event_uid)
            );

            INSERT INTO vacation_new
                (id, user_id, start_date, end_date, source,
                 last_synced, ical_event_uid)
            SELECT id, user_id, start_date, end_date, source,
                   last_synced, ical_event_uid
            FROM vacation;

            DROP TABLE vacation;

            ALTER TABLE vacation_new RENAME TO vacation;

            COMMIT;
        """)

        conn.execute("PRAGMA foreign_keys = ON")
        logger.info("Migration completed: UNIQUE(user_id, ical_event_uid) added")

    except Exception as e:
        conn.execute("ROLLBACK")
        logger.error(f"Migration failed: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    migrate_database()
