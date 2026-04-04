#!/usr/bin/env python3

import sqlite3
import logging
from pathlib import Path
from werkzeug.security import generate_password_hash

# Configure logging
logging.basicConfig(level=logging.INFO)

# Database path
DATABASE_PATH = Path(__file__).parent / "user.db"

def add_authentication_fields():
    """Add password field to user table and set default passwords."""
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        logging.info("Adding authentication fields to user table...")
        
        # Check if password column already exists
        cursor.execute("PRAGMA table_info(user)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'password_hash' not in columns:
            # Add password_hash column
            cursor.execute("ALTER TABLE user ADD COLUMN password_hash TEXT")
            
            # Set default password for existing users (they should change it)
            default_password = generate_password_hash("changeme123")
            cursor.execute("UPDATE user SET password_hash = ? WHERE password_hash IS NULL", (default_password,))
            
            conn.commit()
            logging.info("Password field added successfully")
            logging.info("Default password 'changeme123' set for all existing users")
        else:
            logging.info("Password field already exists")
            
    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    add_authentication_fields()