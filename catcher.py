#!/usr/bin/env -S uv run --script

# /// script
# dependencies = [
#    "requests>=2.25.0",
#    "python-dotenv>=1.0.0",
#    "holidays>=0.34"
# ]
# ///


import os
import json
import requests
import sqlite3
import logging
import time
from typing import Optional, Dict
import datetime
import holidays
import argparse
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load environment variables from .env file
load_dotenv()


def parse_arguments() -> argparse.Namespace:
    """
    Parse command line arguments.
    
    Returns:
        argparse.Namespace: Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="Catcher of the Day - Select and notify the daily catcher"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Perform all checks without updating database or sending notifications"
    )
    return parser.parse_args()

# Validate required environment variables
def validate_environment() -> None:
    """
    Validates that all required environment variables are set.
    Exits the program with an error message if any are missing.
    Only checks variables that don't have defaults.
    """
    required_vars = {
        'SLACK_WEBHOOK_URL': 'Slack webhook URL for notifications'
    }

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

# Constants from environment variables
DATABASE_PATH = os.environ.get('DB_PATH', 'user.db')
HOLIDAY_API_URL = 'https://date.nager.at/Api/v3/IsTodayPublicHoliday/DE?countyCode=DE-BW'
HOLIDAY_TIMEOUT = int(os.environ.get('HOLIDAY_API_TIMEOUT', 2))
SLACK_TIMEOUT = int(os.environ.get('SLACK_API_TIMEOUT', 5))


def is_holiday() -> bool:
    """
    Check if today is a public holiday in Germany (Baden-Württemberg).
    First tries the web service API, then falls back to the holidays library.

    :return: True if today is a public holiday, False otherwise
    :rtype: bool
    """
    # First try the web service
    try:
        response = requests.get(HOLIDAY_API_URL, timeout=HOLIDAY_TIMEOUT)
        if response.status_code == 200:
            logging.info("Holiday detected via web service")
            return True
        elif response.status_code == 204:
            # 204 typically means "no holiday today"
            logging.debug("No holiday today (web service)")
            return False
        else:
            logging.warning(f"Web service returned unexpected status: {response.status_code}")
    except requests.exceptions.RequestException as e:
        logging.warning(f"Web service failed, falling back to holidays library: {e}")

    # Fallback to holidays library
    try:
        # Create holidays object for Germany, Baden-Württemberg
        german_holidays = holidays.Germany(state='BW')
        today = datetime.date.today()

        if today in german_holidays:
            holiday_name = german_holidays.get(today)
            logging.info(f"Holiday detected via fallback library: {holiday_name}")
            return True
        else:
            logging.debug("No holiday today (fallback library)")
            return False
    except Exception as e:
        logging.error(f"Both holiday checking methods failed: {e}")
        # When in doubt, assume it's not a holiday to avoid missing work days
        return False


def trigger_slack(mail: str, max_retries: int = 3, initial_retry_delay: int = 2, dry_run: bool = False) -> None:
    """
    :param mail: The email address of the user to be notified on Slack.
    :type mail: str
    :param max_retries: Maximum number of retry attempts (default: 3)
    :type max_retries: int
    :param initial_retry_delay: Initial delay between retries in seconds (default: 2)
    :type initial_retry_delay: int
    :param dry_run: If True, skip actual notification sending (default: False)
    :type dry_run: bool
    :return: None
    :rtype: None

    This method triggers a Slack notification for the specified user using their email address. It sends a POST request to the configured Slack webhook with the email address as the payload.
    If the request times out or returns a server error (5xx), it will retry up to max_retries times with an increasing delay.

    Example usage:

    ```
    trigger_slack('user@example.com')
    trigger_slack('user@example.com', dry_run=True)  # For testing
    ```

    Note: This method requires the environment variable `SLACK_WEBHOOK_URL` to be properly configured with the Slack webhook URL.
    """
    if mail is None:
        logging.error("Cannot trigger Slack notification: mail is None")
        return

    if dry_run:
        logging.info("[DRY RUN] Would send Slack notification to: %s", mail)
        return

    data: Dict[str, str] = {'uid': mail}
    headers: Dict[str, str] = {'Content-type': 'application/json'}

    webhook_url = os.environ.get('SLACK_WEBHOOK_URL')
    if not webhook_url:
        logging.error("SLACK_WEBHOOK_URL environment variable not set")
        return

    for attempt in range(max_retries):
        # Calculate exponential backoff delay
        retry_delay = initial_retry_delay * (2 ** attempt)

        try:
            response = requests.post(webhook_url, headers=headers, data=json.dumps(data), timeout=SLACK_TIMEOUT)
            if response.status_code == 200:
                logging.info("Chosen Catcher: %s", mail)
                return
            elif 500 <= response.status_code < 600:
                # Retry on server errors (5xx)
                retry_num = attempt + 1
                if retry_num < max_retries:
                    logging.warning(f"Server error {response.status_code}. Retrying ({retry_num}/{max_retries}) in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    logging.error(f"Slack notification failed after {max_retries} attempts: Server error {response.status_code}")
            else:
                logging.warning("Webhook returned: %d (%s)", response.status_code, response.text)
                # Don't retry for other non-5xx errors
                return
        except requests.exceptions.Timeout:
            retry_num = attempt + 1
            if retry_num < max_retries:
                logging.warning(f"Slack notification timed out. Retrying ({retry_num}/{max_retries}) in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                logging.error(f"Slack notification failed after {max_retries} attempts: Timeout")
        except requests.exceptions.RequestException as e:
            logging.error('Failed to trigger Slack notification: %s', e)
            return  # Don't retry for other non-timeout errors

def find_next_catcher(dry_run: bool = False) -> Optional[str]:
    """
    This method `find_next_catcher` is used to retrieve the email address
    of the next user who is available.
    The method retrieves the email address from a database table based
    on specific conditions.

    :param dry_run: If True, don't update the database (default: False)
    :type dry_run: bool
    :return: The email address of the next available user or None
    :rtype: Optional[str]
    """
    try:
        with sqlite3.connect(DATABASE_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            # Check if someone is already chosen for today
            cur.execute("""
                SELECT mail
                FROM user
                WHERE last_chosen = date()
            """)

            result = cur.fetchone()
            if result is None:
                # Find next available user
                cur.execute("""
                    SELECT mail
                    FROM user
                    WHERE weekdays LIKE strftime('%%%w%%','now')
                        AND ((vacation_start IS NULL OR vacation_end IS NULL)
                            OR (date() < vacation_start OR date() > vacation_end))
                    ORDER BY last_chosen ASC
                    LIMIT 1
                """)

                result = cur.fetchone()
                if result is not None:
                    if dry_run:
                        logging.info("[DRY RUN] Would update last_chosen date for: %s", result['mail'])
                    else:
                        # Update the last_chosen date for the selected user
                        cur.execute("UPDATE user SET last_chosen = date() WHERE mail = ?", (result['mail'],))
                        conn.commit()
                    return result['mail']
                else:
                    logging.warning("No available users found for today")
                    return None
            else:
                logging.info("User %s was already selected for today", result['mail'])
                return result['mail']
    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")
        return None


def main() -> None:
    # Parse command line arguments
    args = parse_arguments()
    
    if args.dry_run:
        logging.info("[DRY RUN] Running in dry-run mode - no database changes or notifications will be sent")
    
    # Validate environment variables before proceeding
    validate_environment()

    if is_holiday():
        logging.info("Today is a holiday, no catcher needed")
        return

    mail = find_next_catcher(dry_run=args.dry_run)
    if mail:
        trigger_slack(mail, dry_run=args.dry_run)
    else:
        logging.warning("No catcher found for today")


if __name__ == "__main__":
    main()
