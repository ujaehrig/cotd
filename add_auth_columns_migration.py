#!/usr/bin/env python3
"""
Migration: Add authentication and password reset columns to user table
Migrates from old schema to current schema by adding:
- password_hash TEXT
- password_reset_required INTEGER DEFAULT 0
- password_reset_token TEXT
- password_reset_expires DATETIME
"""

import sqlite3
import sys
import os

def get_db_connection():
    """Get database connection using the same pattern as the main app"""
    db_path = os.path.join(os.path.dirname(__file__), 'user.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def column_exists(conn, table_name, column_name):
    """Check if a column exists in a table"""
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cursor.fetchall()]
    return column_name in columns

def add_auth_columns():
    """Add authentication columns to user table"""
    
    with get_db_connection() as conn:
        try:
            cursor = conn.cursor()
            
            # Check if password_hash column exists
            if not column_exists(conn, 'user', 'password_hash'):
                cursor.execute('ALTER TABLE user ADD COLUMN password_hash TEXT')
                print("✅ Added password_hash column")
            else:
                print("ℹ️  password_hash column already exists")
            
            # Check if password_reset_required column exists
            if not column_exists(conn, 'user', 'password_reset_required'):
                cursor.execute('ALTER TABLE user ADD COLUMN password_reset_required INTEGER DEFAULT 0')
                print("✅ Added password_reset_required column")
            else:
                print("ℹ️  password_reset_required column already exists")
            
            # Check if password_reset_token column exists
            if not column_exists(conn, 'user', 'password_reset_token'):
                cursor.execute('ALTER TABLE user ADD COLUMN password_reset_token TEXT')
                print("✅ Added password_reset_token column")
            else:
                print("ℹ️  password_reset_token column already exists")
            
            # Check if password_reset_expires column exists
            if not column_exists(conn, 'user', 'password_reset_expires'):
                cursor.execute('ALTER TABLE user ADD COLUMN password_reset_expires DATETIME')
                print("✅ Added password_reset_expires column")
            else:
                print("ℹ️  password_reset_expires column already exists")
            
            conn.commit()
            print("🎉 Migration completed successfully!")
            return True
            
        except sqlite3.Error as e:
            print(f"❌ Database error: {e}")
            conn.rollback()
            return False
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            conn.rollback()
            return False

if __name__ == "__main__":
    print("Running migration to add authentication columns...")
    success = add_auth_columns()
    sys.exit(0 if success else 1)