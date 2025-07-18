#!/usr/bin/env python3

import sqlite3
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)

# Database path
DATABASE_PATH = Path(__file__).parent / "user.db"

def add_password_reset_tracking():
    """Add password reset tracking fields to user table."""
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        logging.info("Adding password reset tracking fields to user table...")
        
        # Check if password_reset_required column already exists
        cursor.execute("PRAGMA table_info(user)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'password_reset_required' not in columns:
            # Add password_reset_required column
            cursor.execute("ALTER TABLE user ADD COLUMN password_reset_required INTEGER DEFAULT 0")
            logging.info("Added password_reset_required column")
        
        if 'password_reset_token' not in columns:
            # Add password_reset_token column for future use
            cursor.execute("ALTER TABLE user ADD COLUMN password_reset_token TEXT")
            logging.info("Added password_reset_token column")
        
        if 'password_reset_expires' not in columns:
            # Add password_reset_expires column for future use
            cursor.execute("ALTER TABLE user ADD COLUMN password_reset_expires DATETIME")
            logging.info("Added password_reset_expires column")
        
        conn.commit()
        logging.info("Password reset tracking fields added successfully")
        
    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    add_password_reset_tracking()