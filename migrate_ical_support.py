#!/usr/bin/env -S uv run --script

# /// script
# dependencies = [
#    "python-dotenv>=1.0.0",
# ]
# ///

import sqlite3
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def migrate_database(db_path: str | None = None) -> None:
    """
    Migrate database to support iCal vacation sync.

    Changes:
    - Add ical_url to tenants table
    - Add display_name to user table
    - Add source, last_synced, ical_event_uid to vacations table
    - Create vacation_sync_log table

    Args:
        db_path: Path to database file. If None, uses DB_PATH env var or default.
    """
    if db_path is None:
        from db import DATABASE_PATH
        db_path = DATABASE_PATH

    logger.info(f"Starting iCal migration for database: {db_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Add ical_url to tenants table
        logger.info("Adding ical_url column to tenants table...")
        try:
            cursor.execute("ALTER TABLE tenants ADD COLUMN ical_url TEXT")
            conn.commit()
            logger.info("ical_url column added to tenants")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                logger.info("ical_url column already exists in tenants")
            else:
                raise

        # Add display_name to user table
        logger.info("Adding display_name column to user table...")
        try:
            cursor.execute("ALTER TABLE user ADD COLUMN display_name TEXT")
            conn.commit()
            logger.info("display_name column added to user")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                logger.info("display_name column already exists in user")
            else:
                raise

        # Add columns to vacation table
        logger.info("Adding iCal columns to vacation table...")
        columns_to_add = [
            ("source", "TEXT DEFAULT 'manual'"),
            ("last_synced", "TIMESTAMP"),
            ("ical_event_uid", "TEXT"),
        ]

        for col_name, col_type in columns_to_add:
            try:
                cursor.execute(f"ALTER TABLE vacation ADD COLUMN {col_name} {col_type}")
                conn.commit()
                logger.info(f"{col_name} column added to vacation")
            except sqlite3.OperationalError as e:
                if "duplicate column name" in str(e).lower():
                    logger.info(f"{col_name} column already exists in vacation")
                else:
                    raise

        # Create vacation_sync_log table
        logger.info("Creating vacation_sync_log table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vacation_sync_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id INTEGER NOT NULL,
                sync_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT NOT NULL,
                events_processed INTEGER DEFAULT 0,
                users_matched INTEGER DEFAULT 0,
                error_message TEXT,
                FOREIGN KEY (tenant_id) REFERENCES tenants(id)
            )
        """)
        conn.commit()
        logger.info("vacation_sync_log table created")

        logger.info("iCal migration completed successfully")

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    migrate_database()
