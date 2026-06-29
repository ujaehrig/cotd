#!/usr/bin/env -S uv run --script

# /// script
# dependencies = [
#    "python-dotenv>=1.0.0",
# ]
# ///

import sqlite3
import logging
import os
from pathlib import Path
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
    Migrate database to support multi-tenant architecture.

    Args:
        db_path: Path to database file. If None, uses DB_PATH env var or default.
    """
    if db_path is None:
        from db import DATABASE_PATH
        db_path = DATABASE_PATH

    logger.info(f"Starting migration for database: {db_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check if migration already applied
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='tenants'"
        )
        if cursor.fetchone() is not None:
            logger.info("Migration already applied (tenants table exists)")

            # Check if user table has tenant_id column
            cursor.execute("PRAGMA table_info(user)")
            columns = {row[1] for row in cursor.fetchall()}
            if "tenant_id" in columns:
                logger.info("User table already has tenant_id column")
                return

        # Create tenants table
        logger.info("Creating tenants table...")
        schema_path = Path(__file__).parent / "schema_tenants.sql"
        schema_sql = schema_path.read_text()
        cursor.executescript(schema_sql)
        conn.commit()
        logger.info("Tenants table created")

        # Create default tenant
        webhook_url = os.environ.get(
            "SLACK_WEBHOOK_URL", "https://hooks.slack.com/workflows/PLACEHOLDER"
        )
        location = os.environ.get("HOLIDAY_REGION", "BW")

        logger.info("Creating default tenant 'Team Challengers'...")
        cursor.execute(
            "INSERT OR IGNORE INTO tenants (name, location, webhook_url) VALUES (?, ?, ?)",
            ("Team Challengers", location, webhook_url),
        )
        conn.commit()

        tenant_id = cursor.execute(
            "SELECT id FROM tenants WHERE name = ?", ("Team Challengers",)
        ).fetchone()[0]
        logger.info(f"Default tenant created with id: {tenant_id}")

        # Check if user table exists
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='user'"
        )
        if cursor.fetchone() is None:
            logger.info("User table does not exist yet, skipping user migration")
            return

        # Add tenant_id column to user table
        logger.info("Adding tenant_id column to user table...")
        try:
            cursor.execute(
                "ALTER TABLE user ADD COLUMN tenant_id INTEGER REFERENCES tenants(id)"
            )
            conn.commit()
            logger.info("tenant_id column added")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                logger.info("tenant_id column already exists")
            else:
                raise

        # Assign all existing users to default tenant
        logger.info("Assigning existing users to default tenant...")
        cursor.execute(
            "UPDATE user SET tenant_id = ? WHERE tenant_id IS NULL", (tenant_id,)
        )
        updated_count = cursor.rowcount
        conn.commit()
        logger.info(f"Assigned {updated_count} users to default tenant")

        logger.info("Migration completed successfully")

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    migrate_database()
