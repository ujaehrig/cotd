#!/usr/bin/env -S uv run --script

# /// script
# dependencies = [
#    "python-dotenv>=1.0.0",
# ]
# ///

import sqlite3
import argparse
import logging
import sys
import os
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Database path
DATABASE_PATH = Path(__file__).parent / os.getenv("DB_PATH", "user.db")


def get_db_connection() -> sqlite3.Connection:
    """Create and return a database connection."""
    if not DATABASE_PATH.exists():
        logging.error(f"Database file not found: {DATABASE_PATH}")
        logging.error("Run setup.sh or create the database first")
        sys.exit(1)

    try:
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        logging.error(f"Database connection error: {e}")
        sys.exit(1)


def validate_date(date_str: str) -> str:
    """Validate and format a date string."""
    try:
        # Try to parse the date
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        return date_obj.strftime("%Y-%m-%d")
    except ValueError:
        logging.error(f"Invalid date format: {date_str}. Use YYYY-MM-DD format.")
        sys.exit(1)


def get_user_id_by_email(email: str) -> int:
    """Get user ID by email address."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM user WHERE mail = ?", (email,))
            user = cursor.fetchone()

            if not user:
                logging.error(f"User with email '{email}' not found.")
                sys.exit(1)

            return user['id']
    except sqlite3.Error as e:
        logging.error(f"Error looking up user: {e}")
        sys.exit(1)


def list_users():
    """List all users in the database."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, mail, weekdays, last_chosen FROM user ORDER BY mail"
            )
            users = cursor.fetchall()

            if not users:
                print("No users found in the database.")
                return

            print("\nUsers:")
            print("-" * 80)
            print(f"{'ID':<5} {'Email':<30} {'Weekdays':<10} {'Last Chosen':<12}")
            print("-" * 80)

            for user in users:
                print(
                    f"{user['id']:<5} {user['mail']:<30} {user['weekdays']:<10} {user['last_chosen'] or 'Never':<12}"
                )
    except sqlite3.Error as e:
        logging.error(f"Error listing users: {e}")
        sys.exit(1)


def list_vacations(user_identifier=None):
    """List all vacation periods, optionally filtered by user ID or email."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            if user_identifier:
                # Check if it's a numeric user ID or email
                if isinstance(user_identifier, int) or user_identifier.isdigit():
                    user_id = int(user_identifier)
                    # Check if user exists
                    cursor.execute("SELECT mail FROM user WHERE id = ?", (user_id,))
                    user = cursor.fetchone()
                    if not user:
                        logging.error(f"User with ID {user_id} not found.")
                        sys.exit(1)
                else:
                    # It's an email address
                    user_id = get_user_id_by_email(user_identifier)
                    cursor.execute("SELECT mail FROM user WHERE id = ?", (user_id,))
                    user = cursor.fetchone()

                print(f"\nVacation periods for user: {user['mail']}")
                cursor.execute(
                    """
                    SELECT v.id, u.mail, v.start_date, v.end_date
                    FROM vacation v
                    JOIN user u ON v.user_id = u.id
                    WHERE v.user_id = ?
                    ORDER BY v.start_date
                """,
                    (user_id,),
                )
            else:
                print("\nAll vacation periods:")
                cursor.execute("""
                    SELECT v.id, u.mail, v.start_date, v.end_date
                    FROM vacation v
                    JOIN user u ON v.user_id = u.id
                    ORDER BY v.start_date, u.mail
                """)

            vacations = cursor.fetchall()

            if not vacations:
                print("No vacation periods found.")
                return

            print("-" * 80)
            print(f"{'ID':<5} {'Email':<30} {'Start Date':<12} {'End Date':<12}")
            print("-" * 80)

            for vacation in vacations:
                print(
                    f"{vacation['id']:<5} {vacation['mail']:<30} {vacation['start_date']:<12} {vacation['end_date']:<12}"
                )
    except sqlite3.Error as e:
        logging.error(f"Error listing vacations: {e}")
        sys.exit(1)


def add_vacation(user_identifier, start_date, end_date=None):
    """
    Add a new vacation period for a user.

    user_identifier can be either a user ID (int) or email address (str).
    If end_date is not provided, it will be set to the same as start_date (single day vacation).
    """
    # Resolve user identifier to user ID
    if isinstance(user_identifier, int) or (isinstance(user_identifier, str) and user_identifier.isdigit()):
        user_id = int(user_identifier)
    else:
        # It's an email address
        user_id = get_user_id_by_email(user_identifier)

    # Validate start date
    start = validate_date(start_date)

    # If end_date is not provided, use start_date (single day vacation)
    if end_date is None:
        end = start
        single_day = True
    else:
        end = validate_date(end_date)
        single_day = False

    # Check that end date is not before start date
    if start > end:
        logging.error("End date cannot be before start date.")
        sys.exit(1)

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Check if user exists and get email
            cursor.execute("SELECT mail FROM user WHERE id = ?", (user_id,))
            user = cursor.fetchone()
            if not user:
                logging.error(f"User with ID {user_id} not found.")
                sys.exit(1)

            # Add vacation period
            cursor.execute(
                """
                INSERT INTO vacation (user_id, start_date, end_date)
                VALUES (?, ?, ?)
            """,
                (user_id, start, end),
            )

            conn.commit()

            if single_day:
                logging.info(f"Single day vacation added for {user['mail']} on {start}")
            else:
                logging.info(f"Vacation period added for {user['mail']} from {start} to {end}")
    except sqlite3.Error as e:
        logging.error(f"Error adding vacation: {e}")
        sys.exit(1)


def delete_vacation(vacation_id):
    """Delete a vacation period by ID."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Check if vacation exists
            cursor.execute(
                """
                SELECT v.id, u.mail, v.start_date, v.end_date
                FROM vacation v
                JOIN user u ON v.user_id = u.id
                WHERE v.id = ?
            """,
                (vacation_id,),
            )

            vacation = cursor.fetchone()
            if not vacation:
                logging.error(f"Vacation with ID {vacation_id} not found.")
                sys.exit(1)

            # Delete vacation
            cursor.execute("DELETE FROM vacation WHERE id = ?", (vacation_id,))
            conn.commit()

            # Check if it was a single day vacation
            if vacation['start_date'] == vacation['end_date']:
                logging.info(f"Deleted single day vacation for {vacation['mail']} on {vacation['start_date']}")
            else:
                logging.info(
                    f"Deleted vacation period for {vacation['mail']} from {vacation['start_date']} to {vacation['end_date']}"
                )
    except sqlite3.Error as e:
        logging.error(f"Error deleting vacation: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Manage vacation periods for users")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # List users command
    subparsers.add_parser("list-users", help="List all users")

    # List vacations command
    list_vacations_parser = subparsers.add_parser(
        "list-vacations", help="List vacation periods"
    )
    list_vacations_parser.add_argument(
        "-u", "--user", help="Filter by user ID or email address"
    )

    # Add vacation command
    add_vacation_parser = subparsers.add_parser("add", help="Add a new vacation period")
    add_vacation_parser.add_argument("user", help="User ID or email address")
    add_vacation_parser.add_argument("start_date", help="Start date (YYYY-MM-DD)")
    add_vacation_parser.add_argument("end_date", help="End date (YYYY-MM-DD)", nargs='?', default=None)

    # Delete vacation command
    delete_vacation_parser = subparsers.add_parser(
        "delete", help="Delete a vacation period"
    )
    delete_vacation_parser.add_argument(
        "vacation_id", type=int, help="Vacation ID to delete"
    )

    args = parser.parse_args()

    if args.command == "list-users":
        list_users()
    elif args.command == "list-vacations":
        list_vacations(args.user)
    elif args.command == "add":
        add_vacation(args.user, args.start_date, args.end_date)
    elif args.command == "delete":
        delete_vacation(args.vacation_id)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
