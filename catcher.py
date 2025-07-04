#!/usr/bin/env -S uv run --script

# /// script
# dependencies = [
#    "requests>=2.25.0",
#    "python-dotenv>=1.0.0"
# ]
# ///

import os
import json
import requests
import sqlite3
import logging
import time
import datetime
from typing import Optional, Dict, Tuple
from pathlib import Path
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(Path(__file__).parent / "catcher.log"),
    ],
)

# Load environment variables from .env file
load_dotenv()

# Constants
DATABASE_PATH = os.environ.get("DB_PATH", str(Path(__file__).parent / "user.db"))
HOLIDAY_API_URL = os.environ.get(
    "HOLIDAY_API_URL",
    "https://date.nager.at/Api/v3/IsTodayPublicHoliday/DE?countyCode=DE-BW",
)
HOLIDAY_TIMEOUT = int(os.environ.get("HOLIDAY_API_TIMEOUT", "5"))  # seconds
SLACK_TIMEOUT = int(os.environ.get("SLACK_API_TIMEOUT", "10"))  # seconds


def validate_environment() -> None:
    """
    Validates that all required environment variables are set.
    Exits the program with an error message if any are missing.
    """
    required_vars = {"SLACK_WEBHOOK_URL": "Slack webhook URL for notifications"}

    missing_vars = []
    for var, description in required_vars.items():
        if not os.environ.get(var):
            missing_vars.append(f"- {var}: {description}")

    if missing_vars:
        logging.error("Missing required environment variables:")
        for var in missing_vars:
            logging.error(var)
        logging.error("Please set these variables in your .env file or environment")
        exit(1)

    logging.debug("Environment validation successful")


def is_weekend() -> bool:
    """
    Check if today is a weekend (Saturday or Sunday).

    Returns:
        bool: True if today is a weekend, False otherwise
    """
    return datetime.datetime.now().weekday() >= 5  # 5 = Saturday, 6 = Sunday


def is_holiday() -> bool:
    """
    Check if today is a public holiday in Germany (Baden-Württemberg).

    Returns:
        bool: True if today is a public holiday, False otherwise
    """
    try:
        response = requests.get(HOLIDAY_API_URL, timeout=HOLIDAY_TIMEOUT)
        if response.status_code == 200:
            logging.info("Holiday detected")
            return True
        return False
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to check holiday status: {e}")
        return False


def trigger_slack(
    mail: str, max_retries: int = 3, initial_retry_delay: int = 2
) -> bool:
    """
    Trigger a Slack notification for the specified user.

    Args:
        mail: The email address of the user to be notified
        max_retries: Maximum number of retry attempts
        initial_retry_delay: Initial delay between retries in seconds

    Returns:
        bool: True if notification was successful, False otherwise
    """
    if not mail:
        logging.error("Cannot trigger Slack notification: mail is None")
        return False

    data: Dict[str, str] = {"uid": mail}
    headers: Dict[str, str] = {"Content-type": "application/json"}

    webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook_url:
        logging.error("SLACK_WEBHOOK_URL environment variable not set")
        return False

    for attempt in range(max_retries):
        # Calculate exponential backoff delay
        retry_delay = initial_retry_delay * (2**attempt)

        try:
            response = requests.post(
                webhook_url,
                headers=headers,
                data=json.dumps(data),
                timeout=SLACK_TIMEOUT,
            )
            if response.status_code == 200:
                logging.info(f"Slack notification sent successfully for: {mail}")
                return True
            elif 500 <= response.status_code < 600:
                # Retry on server errors (5xx)
                retry_num = attempt + 1
                if retry_num < max_retries:
                    logging.warning(
                        f"Server error {response.status_code}. Retrying ({retry_num}/{max_retries}) in {retry_delay} seconds..."
                    )
                    time.sleep(retry_delay)
                else:
                    logging.error(
                        f"Slack notification failed after {max_retries} attempts: Server error {response.status_code}"
                    )
                    return False
            else:
                logging.warning(
                    f"Webhook returned: {response.status_code} ({response.text})"
                )
                # Don't retry for other non-5xx errors
                return False
        except requests.exceptions.Timeout:
            retry_num = attempt + 1
            if retry_num < max_retries:
                logging.warning(
                    f"Slack notification timed out. Retrying ({retry_num}/{max_retries}) in {retry_delay} seconds..."
                )
                time.sleep(retry_delay)
            else:
                logging.error(
                    f"Slack notification failed after {max_retries} attempts: Timeout"
                )
                return False
        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to trigger Slack notification: {e}")
            return False

    return False


def get_db_connection() -> sqlite3.Connection:
    """
    Create and return a database connection with proper settings.

    Returns:
        sqlite3.Connection: Database connection object

    Raises:
        sqlite3.Error: If there's an error connecting to the database
    """
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        logging.error(f"Database connection error: {e}")
        raise


def is_user_on_vacation(conn: sqlite3.Connection, user_id: int, date: str) -> bool:
    """
    Check if a user is on vacation on a specific date.

    Args:
        conn: Database connection
        user_id: User ID to check
        date: Date to check in ISO format (YYYY-MM-DD)

    Returns:
        bool: True if the user is on vacation, False otherwise
    """
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT COUNT(*) 
            FROM vacation 
            WHERE user_id = ? 
              AND ? BETWEEN start_date AND end_date
        """,
            (user_id, date),
        )

        count = cursor.fetchone()[0]
        return count > 0
    except sqlite3.Error as e:
        logging.error(f"Error checking vacation status: {e}")
        return False


def find_next_catcher() -> Tuple[Optional[str], bool]:
    """
    Find the next available user to be the catcher of the day.

    Returns:
        Tuple[Optional[str], bool]: A tuple containing:
            - The email address of the next available user or None
            - Boolean indicating if a new user was selected (True) or if we're using a previously selected user (False)
    """
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            today = datetime.date.today().isoformat()

            # Check if someone is already chosen for today
            cur.execute(
                """
                SELECT mail 
                FROM user
                WHERE last_chosen = ?
            """,
                (today,),
            )

            result = cur.fetchone()
            if result is not None:
                logging.info(f"User {result['mail']} was already selected for today")
                return result["mail"], False

            # Get current weekday (0-6, where 0 is Monday in SQLite's strftime)
            weekday = datetime.datetime.now().strftime("%w")

            # Get all users who are available on this weekday
            cur.execute(
                """
                SELECT id, mail 
                FROM user 
                WHERE weekdays LIKE ?
                ORDER BY last_chosen ASC
            """,
                (f"%{weekday}%",),
            )

            available_users = cur.fetchall()

            # Filter out users who are on vacation
            for user in available_users:
                if not is_user_on_vacation(conn, user["id"], today):
                    # Found an available user who is not on vacation
                    # Update the last_chosen date for the selected user
                    cur.execute(
                        "UPDATE user SET last_chosen = ? WHERE id = ?",
                        (today, user["id"]),
                    )
                    conn.commit()
                    logging.info(f"Selected new catcher: {user['mail']}")
                    return user["mail"], True

            logging.warning(
                "No available users found for today (all on vacation or not scheduled)"
            )
            return None, False
    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")
        return None, False


def main() -> None:
    """
    Main function to run the Catcher of the Day process.
    """
    try:
        # Validate environment variables
        validate_environment()

        # Check if today is a non-working day
        if is_weekend():
            logging.info("Today is a weekend, no catcher needed")
            return

        if is_holiday():
            logging.info("Today is a holiday, no catcher needed")
            return

        # Find next catcher
        mail, is_new_selection = find_next_catcher()
        if mail:
            if is_new_selection:
                # Only trigger Slack if this is a new selection
                success = trigger_slack(mail)
                if success:
                    logging.info(f"Successfully notified catcher: {mail}")
                else:
                    logging.error(f"Failed to notify catcher: {mail}")
            else:
                logging.info(f"Using previously selected catcher: {mail}")
        else:
            logging.warning("No catcher found for today")
    except Exception as e:
        logging.error(f"Unexpected error: {e}", exc_info=True)


if __name__ == "__main__":
    main()
