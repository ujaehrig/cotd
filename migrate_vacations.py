#!/usr/bin/env -S uv run --script

import sqlite3
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Database path
DATABASE_PATH = Path(__file__).parent / "user.db"


def migrate_vacations():
    """
    Migrate the database schema to support multiple vacation periods per user.

    This script:
    1. Creates a new 'vacation' table
    2. Migrates existing vacation data from the 'user' table to the new 'vacation' table
    3. Removes the vacation columns from the 'user' table
    """
    try:
        # Connect to the database
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        logging.info("Starting database migration for multiple vacation periods...")

        # Check if the vacation table already exists
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='vacation'"
        )
        if cursor.fetchone():
            logging.info("Vacation table already exists. Migration already completed.")
            return

        # Create the new vacation table
        logging.info("Creating vacation table...")
        cursor.execute("""
        CREATE TABLE vacation (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            start_date DATE NOT NULL,
            end_date DATE NOT NULL,
            FOREIGN KEY (user_id) REFERENCES user(id)
        )
        """)

        # Migrate existing vacation data
        logging.info("Migrating existing vacation data...")
        cursor.execute("""
        INSERT INTO vacation (user_id, start_date, end_date)
        SELECT id, vacation_start, vacation_end
        FROM user
        WHERE vacation_start IS NOT NULL AND vacation_end IS NOT NULL
        """)

        # Count migrated records
        cursor.execute("SELECT COUNT(*) FROM vacation")
        migrated_count = cursor.fetchone()[0]
        logging.info(f"Migrated {migrated_count} vacation periods")

        # Remove the old vacation columns from the user table
        logging.info("Removing old vacation columns from user table...")

        # Create a temporary table without the vacation columns
        cursor.execute("""
        CREATE TABLE user_temp (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            weekdays varchar(10),
            mail varchar(50) UNIQUE NOT NULL,
            last_chosen date
        )
        """)

        # Copy data to the temporary table
        cursor.execute("""
        INSERT INTO user_temp (id, weekdays, mail, last_chosen)
        SELECT id, weekdays, mail, last_chosen FROM user
        """)

        # Drop the original table
        cursor.execute("DROP TABLE user")

        # Rename the temporary table to the original name
        cursor.execute("ALTER TABLE user_temp RENAME TO user")

        # Commit the changes
        conn.commit()
        logging.info("Migration completed successfully")

    except sqlite3.Error as e:
        logging.error(f"Database error during migration: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    migrate_vacations()
