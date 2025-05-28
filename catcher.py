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
from typing import Optional, Dict, List, Any, Union
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load environment variables from .env file
load_dotenv()

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
    Checks if today is a public holiday in Germany.

    :return: True if today is a public holiday, False otherwise
    :rtype: bool
    """
    try:
        response = requests.get(HOLIDAY_API_URL, timeout=HOLIDAY_TIMEOUT)
        if response.status_code == 200:
            logging.info('Holiday detected')
        return response.status_code == 200
    except requests.exceptions.RequestException as e:
        logging.error('Failed to check holiday status: %s', e)
        return False


def trigger_slack(mail: str, max_retries: int = 3, retry_delay: int = 2) -> None:
    """
    :param mail: The email address of the user to be notified on Slack.
    :type mail: str
    :param max_retries: Maximum number of retry attempts (default: 3)
    :type max_retries: int
    :param retry_delay: Delay between retries in seconds (default: 2)
    :type retry_delay: int
    :return: None
    :rtype: None

    This method triggers a Slack notification for the specified user using their email address. It sends a POST request to the configured Slack webhook with the email address as the payload.
    If the request times out, it will retry up to max_retries times.

    Example usage:

    ```
    trigger_slack('user@example.com')
    ```

    Note: This method requires the environment variable `SLACK_WEBHOOK_URL` to be properly configured with the Slack webhook URL.
    """
    if mail is None:
        logging.error("Cannot trigger Slack notification: mail is None")
        return
        
    data: Dict[str, str] = {'uid': mail}
    headers: Dict[str, str] = {'Content-type': 'application/json'}
    
    webhook_url = os.environ.get('SLACK_WEBHOOK_URL')
    if not webhook_url:
        logging.error("SLACK_WEBHOOK_URL environment variable not set")
        return
    
    for attempt in range(max_retries):
        try:
            response = requests.post(webhook_url, headers=headers, data=json.dumps(data), timeout=SLACK_TIMEOUT)
            if response.status_code == 200:
                logging.info("Chosen Catcher: %s", mail)
                return
            else:
                logging.warning("Webhook returned: %d (%s)", response.status_code, response.text)
                # Don't retry for non-timeout errors that returned a status code
                return
        except requests.exceptions.Timeout:
            retry_num = attempt + 1
            if retry_num < max_retries:
                logging.warning(f"Slack notification timed out. Retrying ({retry_num}/{max_retries})...")
                time.sleep(retry_delay)
            else:
                logging.error(f"Slack notification failed after {max_retries} attempts")
        except requests.exceptions.RequestException as e:
            logging.error('Failed to trigger Slack notification: %s', e)
            return  # Don't retry for non-timeout errors

def find_next_catcher() -> Optional[str]:
    """
    This method `find_next_catcher` is used to retrieve the email address
    of the next user who is available.
    The method retrieves the email address from a database table based
    on specific conditions.

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
                    # Update the last_chosen date for the selected user
                    cur.execute("UPDATE user SET last_chosen = date() WHERE mail = ?", (result['mail'],))
                    conn.commit()
                    return result['mail']
                else:
                    logging.warning("No available users found for today")
                    return None
            else:
                return result['mail']
    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")
        return None


def main() -> None:
    # Validate environment variables before proceeding
    validate_environment()
    
    if is_holiday():
        logging.info("Today is a holiday, no catcher needed")
        return

    mail = find_next_catcher()
    if mail:
        trigger_slack(mail)
    else:
        logging.warning("No catcher found for today")


if __name__ == "__main__":
    main()

