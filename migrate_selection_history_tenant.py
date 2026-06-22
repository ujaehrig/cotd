#!/usr/bin/env -S uv run --script

# /// script
# dependencies = [
#    "python-dotenv>=1.0.0",
# ]
# ///

"""
Migration script to add tenant_id to selection_history and remove user.last_chosen.

This script:
1. Adds tenant_id column to selection_history (NOT NULL, FK to tenants)
2. Backfills tenant_id from current user.tenant_id
3. Adds index on (tenant_id, selected_date)
4. Drops user.last_chosen column
"""

import logging
import sqlite3
import sys
from pathlib import Path

from dotenv import load_dotenv

from db import DATABASE_PATH, get_db_connection

load_dotenv()

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def has_column(cursor, table, column):
    """Check if a column exists in a table."""
    cursor.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cursor.fetchall())


def step_add_tenant_id(cursor):
    """Add tenant_id column and backfill from user.tenant_id."""
    if has_column(cursor, "selection_history", "tenant_id"):
        logging.info("selection_history.tenant_id already exists, skipping")
        return

    logging.info("Adding tenant_id column to selection_history...")

    # Add as nullable first so we can backfill
    cursor.execute("ALTER TABLE selection_history ADD COLUMN tenant_id INTEGER")

    # Backfill from user.tenant_id
    cursor.execute("""
        UPDATE selection_history
        SET tenant_id = (SELECT tenant_id FROM user WHERE user.id = selection_history.user_id)
    """)

    # Check for any NULLs (orphaned records)
    cursor.execute("SELECT COUNT(*) FROM selection_history WHERE tenant_id IS NULL")
    null_count = cursor.fetchone()[0]
    if null_count > 0:
        logging.warning(
            f"{null_count} selection_history rows have no matching user, "
            "deleting orphaned records"
        )
        cursor.execute("DELETE FROM selection_history WHERE tenant_id IS NULL")

    logging.info("Backfill complete")


def step_enforce_not_null(cursor):
    """Recreate table to enforce NOT NULL and FK on tenant_id."""
    # Check if already NOT NULL by inspecting schema
    cursor.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='selection_history'"
    )
    schema = cursor.fetchone()[0]
    if "tenant_id INTEGER NOT NULL" in schema:
        logging.info("tenant_id already NOT NULL, skipping table rebuild")
        return

    logging.info("Rebuilding selection_history to enforce NOT NULL on tenant_id...")

    cursor.execute("""
        CREATE TABLE selection_history_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            selected_date DATE NOT NULL,
            tenant_id INTEGER NOT NULL,
            FOREIGN KEY (user_id) REFERENCES user(id),
            FOREIGN KEY (tenant_id) REFERENCES tenants(id)
        )
    """)

    cursor.execute("""
        INSERT INTO selection_history_new (id, user_id, selected_date, tenant_id)
        SELECT id, user_id, selected_date, tenant_id FROM selection_history
    """)

    cursor.execute("DROP TABLE selection_history")
    cursor.execute("ALTER TABLE selection_history_new RENAME TO selection_history")

    logging.info("Table rebuilt with NOT NULL constraint")


def step_create_indexes(cursor):
    """Create indexes on the new table."""
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='index' AND name='idx_selection_history_tenant_date'
    """)
    if cursor.fetchone():
        logging.info("Index idx_selection_history_tenant_date already exists")
    else:
        logging.info("Creating index on (tenant_id, selected_date)...")
        cursor.execute("""
            CREATE INDEX idx_selection_history_tenant_date
            ON selection_history(tenant_id, selected_date)
        """)

    # Recreate original indexes (lost during table rebuild)
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='index' AND name='idx_selection_history_user_date'
    """)
    if not cursor.fetchone():
        cursor.execute("""
            CREATE INDEX idx_selection_history_user_date
            ON selection_history(user_id, selected_date)
        """)

    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='index' AND name='idx_selection_history_date'
    """)
    if not cursor.fetchone():
        cursor.execute("""
            CREATE INDEX idx_selection_history_date
            ON selection_history(selected_date)
        """)


def step_drop_last_chosen(cursor):
    """Drop the last_chosen column from user table."""
    if not has_column(cursor, "user", "last_chosen"):
        logging.info("user.last_chosen already removed, skipping")
        return

    logging.info("Dropping user.last_chosen column...")
    cursor.execute("ALTER TABLE user DROP COLUMN last_chosen")
    logging.info("user.last_chosen removed")


def main():
    """Run the migration."""
    if not Path(DATABASE_PATH).exists():
        logging.error(f"Database file {DATABASE_PATH} not found")
        sys.exit(1)

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            logging.info("Starting selection_history tenant migration...")

            step_add_tenant_id(cursor)
            step_enforce_not_null(cursor)
            step_create_indexes(cursor)
            step_drop_last_chosen(cursor)

            conn.commit()
            logging.info("Migration completed successfully!")

    except sqlite3.Error as e:
        logging.error(f"Database error during migration: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
