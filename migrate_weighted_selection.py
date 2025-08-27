#!/usr/bin/env python3

"""
Migration script to add selection history tracking for weighted selection algorithm.

This script:
1. Creates a new selection_history table
2. Populates it with existing last_chosen data
3. Adds indexes for performance
"""

import sqlite3
import logging
import sys
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

DATABASE_PATH = "user.db"


def get_db_connection():
    """Create and return a database connection."""
    return sqlite3.connect(DATABASE_PATH)


def check_migration_needed(cursor):
    """Check if migration is needed by looking for selection_history table."""
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='selection_history'
    """)
    return cursor.fetchone() is None


def create_selection_history_table(cursor):
    """Create the selection_history table."""
    logging.info("Creating selection_history table...")
    cursor.execute("""
        CREATE TABLE selection_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            selected_date DATE NOT NULL,
            FOREIGN KEY (user_id) REFERENCES user(id)
        )
    """)
    
    # Add index for performance
    cursor.execute("""
        CREATE INDEX idx_selection_history_user_date 
        ON selection_history(user_id, selected_date)
    """)
    
    cursor.execute("""
        CREATE INDEX idx_selection_history_date 
        ON selection_history(selected_date)
    """)


def migrate_existing_data(cursor):
    """Migrate existing last_chosen data to selection_history."""
    logging.info("Migrating existing last_chosen data...")
    
    cursor.execute("""
        INSERT INTO selection_history (user_id, selected_date)
        SELECT id, last_chosen
        FROM user
        WHERE last_chosen IS NOT NULL
    """)
    
    # Count migrated records
    cursor.execute("SELECT COUNT(*) FROM selection_history")
    migrated_count = cursor.fetchone()[0]
    logging.info(f"Migrated {migrated_count} selection records")


def main():
    """Run the migration."""
    try:
        # Check if database exists
        if not Path(DATABASE_PATH).exists():
            logging.error(f"Database file {DATABASE_PATH} not found")
            sys.exit(1)
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Check if migration is needed
            if not check_migration_needed(cursor):
                logging.info("Migration already completed - selection_history table exists")
                return
            
            logging.info("Starting weighted selection migration...")
            
            # Create new table
            create_selection_history_table(cursor)
            
            # Migrate existing data
            migrate_existing_data(cursor)
            
            # Commit changes
            conn.commit()
            
            logging.info("Migration completed successfully!")
            logging.info("You can now use the enhanced weighted selection algorithm")
            
    except sqlite3.Error as e:
        logging.error(f"Database error during migration: {e}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Unexpected error during migration: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
