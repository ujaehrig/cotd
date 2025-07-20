#!/usr/bin/env -S uv run --script

# /// script
# dependencies = [
#     "requests>=2.25.0",
#     "python-dotenv>=1.0.0"
# ]
# ///

import os
import json
import requests
import logging
import time
from typing import Optional, Dict
from datetime import datetime


def send_vacation_webhook(
    webhook_url: str,
    event_type: str,
    user_email: str,
    start_date: str,
    end_date: str,
    max_retries: int = 3,
    initial_retry_delay: int = 2,
    timeout: int = 10
) -> bool:
    """
    Send a vacation webhook notification.

    Args:
        webhook_url: The webhook URL to send the notification to
        event_type: Type of event ('vacation_added' or 'vacation_deleted')
        user_email: Email address of the user
        start_date: Start date of the vacation (YYYY-MM-DD)
        end_date: End date of the vacation (YYYY-MM-DD)
        max_retries: Maximum number of retry attempts
        initial_retry_delay: Initial delay between retries in seconds
        timeout: Request timeout in seconds

    Returns:
        bool: True if notification was successful, False otherwise
    """
    if not webhook_url:
        logging.debug(f"No webhook URL configured for {event_type}")
        return False

    if not user_email:
        logging.error(f"Cannot send {event_type} webhook: user_email is None")
        return False

    # Calculate vacation duration
    try:
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        duration_days = (end_dt - start_dt).days + 1
    except ValueError as e:
        logging.error(f"Invalid date format in webhook data: {e}")
        return False

    # Prepare webhook payload
    data: Dict[str, str] = {
        "event": event_type,
        "user_email": user_email,
        "start_date": start_date,
        "end_date": end_date,
        "duration_days": str(duration_days),
        "timestamp": datetime.now().isoformat()
    }

    # Add human-readable message
    if duration_days == 1:
        duration_text = "1 day"
    else:
        duration_text = f"{duration_days} days"

    if event_type == "vacation_added":
        data["message"] = f"{user_email} added vacation: {start_date} to {end_date} ({duration_text})"
    elif event_type == "vacation_deleted":
        data["message"] = f"{user_email} deleted vacation: {start_date} to {end_date} ({duration_text})"

    headers: Dict[str, str] = {"Content-type": "application/json"}

    for attempt in range(max_retries):
        # Calculate exponential backoff delay
        retry_delay = initial_retry_delay * (2**attempt)

        try:
            response = requests.post(
                webhook_url,
                headers=headers,
                data=json.dumps(data),
                timeout=timeout,
            )
            
            if response.status_code == 200:
                logging.info(f"{event_type} webhook sent successfully for: {user_email}")
                return True
            elif 500 <= response.status_code < 600:
                # Retry on server errors (5xx)
                retry_num = attempt + 1
                if retry_num < max_retries:
                    logging.warning(
                        f"Webhook server error {response.status_code}. Retrying ({retry_num}/{max_retries}) in {retry_delay} seconds..."
                    )
                    time.sleep(retry_delay)
                else:
                    logging.error(
                        f"{event_type} webhook failed after {max_retries} attempts: Server error {response.status_code}"
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
                    f"{event_type} webhook timed out. Retrying ({retry_num}/{max_retries}) in {retry_delay} seconds..."
                )
                time.sleep(retry_delay)
            else:
                logging.error(f"{event_type} webhook failed after {max_retries} timeout attempts")
                return False
                
        except requests.exceptions.RequestException as e:
            retry_num = attempt + 1
            if retry_num < max_retries:
                logging.warning(
                    f"{event_type} webhook request failed: {e}. Retrying ({retry_num}/{max_retries}) in {retry_delay} seconds..."
                )
                time.sleep(retry_delay)
            else:
                logging.error(f"{event_type} webhook failed after {max_retries} attempts: {e}")
                return False

    return False


def send_vacation_added_webhook(user_email: str, start_date: str, end_date: str) -> bool:
    """
    Send a webhook notification when a vacation is added.

    Args:
        user_email: Email address of the user
        start_date: Start date of the vacation (YYYY-MM-DD)
        end_date: End date of the vacation (YYYY-MM-DD)

    Returns:
        bool: True if notification was successful, False otherwise
    """
    webhook_url = os.environ.get("VACATION_ADDED_WEBHOOK_URL")
    return send_vacation_webhook(
        webhook_url=webhook_url,
        event_type="vacation_added",
        user_email=user_email,
        start_date=start_date,
        end_date=end_date
    )


def send_vacation_deleted_webhook(user_email: str, start_date: str, end_date: str) -> bool:
    """
    Send a webhook notification when a vacation is deleted.

    Args:
        user_email: Email address of the user
        start_date: Start date of the vacation (YYYY-MM-DD)
        end_date: End date of the vacation (YYYY-MM-DD)

    Returns:
        bool: True if notification was successful, False otherwise
    """
    webhook_url = os.environ.get("VACATION_DELETED_WEBHOOK_URL")
    return send_vacation_webhook(
        webhook_url=webhook_url,
        event_type="vacation_deleted",
        user_email=user_email,
        start_date=start_date,
        end_date=end_date
    )
