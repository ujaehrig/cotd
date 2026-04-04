#!/usr/bin/env python3

import sqlite3
import argparse
import logging
import sys
import getpass
import secrets
import string
from pathlib import Path
from werkzeug.security import generate_password_hash

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Database path
DATABASE_PATH = Path(__file__).parent / "user.db"

def get_db_connection() -> sqlite3.Connection:
    """Create and return a database connection."""
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        logging.error(f"Database connection error: {e}")
        sys.exit(1)

def generate_random_password(length=12):
    """Generate a random password with letters, digits, and special characters."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def reset_user_password(email, new_password=None, generate_random=False):
    """Reset a user's password."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Check if user exists
            cursor.execute("SELECT id, mail FROM user WHERE mail = ?", (email,))
            user = cursor.fetchone()
            
            if not user:
                logging.error(f"User with email '{email}' not found.")
                return False
            
            # Generate random password if requested
            if generate_random:
                new_password = generate_random_password()
                logging.info(f"Generated random password: {new_password}")
            
            # Hash the new password
            password_hash = generate_password_hash(new_password)
            
            # Update the password and set reset required flag
            cursor.execute(
                "UPDATE user SET password_hash = ?, password_reset_required = 1 WHERE mail = ?",
                (password_hash, email)
            )
            
            conn.commit()
            logging.info(f"Password reset successfully for user: {email}")
            
            if generate_random:
                print(f"\nNew password for {email}: {new_password}")
                print("Please provide this password to the user and ask them to change it after login.")
            
            return True
            
    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")
        return False

def list_users():
    """List all users for password reset reference."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT mail FROM user ORDER BY mail")
            users = cursor.fetchall()
            
            if not users:
                print("No users found in the database.")
                return
            
            print("\nUsers in the system:")
            print("-" * 40)
            for user in users:
                print(f"  {user['mail']}")
            print("-" * 40)
            
    except sqlite3.Error as e:
        logging.error(f"Error listing users: {e}")

def interactive_password_reset():
    """Interactive password reset process."""
    print("\n=== Password Reset Tool ===")
    
    # List users first
    list_users()
    
    # Get user email
    email = input("\nEnter user email to reset password: ").strip()
    
    if not email:
        print("Email cannot be empty.")
        return
    
    # Ask for password option
    print("\nPassword options:")
    print("1. Enter new password manually")
    print("2. Generate random password")
    
    choice = input("Choose option (1 or 2): ").strip()
    
    if choice == "1":
        # Manual password entry
        new_password = getpass.getpass("Enter new password: ")
        confirm_password = getpass.getpass("Confirm new password: ")
        
        if new_password != confirm_password:
            print("Passwords do not match!")
            return
        
        if len(new_password) < 6:
            print("Password must be at least 6 characters long!")
            return
        
        success = reset_user_password(email, new_password)
        
    elif choice == "2":
        # Generate random password
        success = reset_user_password(email, generate_random=True)
        
    else:
        print("Invalid choice!")
        return
    
    if success:
        print(f"\nPassword reset completed for: {email}")
    else:
        print(f"\nPassword reset failed for: {email}")

def main():
    parser = argparse.ArgumentParser(description="Reset user passwords")
    parser.add_argument("--email", help="User email address")
    parser.add_argument("--password", help="New password (will prompt if not provided)")
    parser.add_argument("--generate", action="store_true", help="Generate random password")
    parser.add_argument("--list", action="store_true", help="List all users")
    parser.add_argument("--interactive", action="store_true", help="Interactive mode")
    
    args = parser.parse_args()
    
    if args.list:
        list_users()
        return
    
    if args.interactive:
        interactive_password_reset()
        return
    
    if not args.email:
        print("No email provided. Use --interactive mode or provide --email")
        print("Use --help for more options")
        return
    
    if args.generate:
        success = reset_user_password(args.email, generate_random=True)
    else:
        if args.password:
            new_password = args.password
        else:
            new_password = getpass.getpass(f"Enter new password for {args.email}: ")
        
        if len(new_password) < 6:
            print("Password must be at least 6 characters long!")
            return
        
        success = reset_user_password(args.email, new_password)
    
    if success:
        print(f"Password reset completed for: {args.email}")
    else:
        print(f"Password reset failed for: {args.email}")

if __name__ == "__main__":
    main()