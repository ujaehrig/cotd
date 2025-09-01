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
import datetime
import holidays
import argparse
import random
from typing import Optional, Dict, Tuple, List
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


def parse_arguments() -> argparse.Namespace:
    """
    Parse command line arguments.
    
    Returns:
        argparse.Namespace: Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="Catcher of the Day - Select and notify the daily catcher (Enhanced Weighted Algorithm)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Perform all checks without updating database or sending notifications"
    )
    parser.add_argument(
        "--debug-weights",
        action="store_true",
        help="Show weight calculations for all eligible users"
    )
    return parser.parse_args()

# Constants
DATABASE_PATH = os.environ.get("DB_PATH", str(Path(__file__).parent / "user.db"))
HOLIDAY_API_URL = os.environ.get(
    "HOLIDAY_API_URL",
    "https://date.nager.at/Api/v3/IsTodayPublicHoliday/DE?countyCode=DE-BW",
)
HOLIDAY_TIMEOUT = int(os.environ.get("HOLIDAY_API_TIMEOUT", "5"))  # seconds
HOLIDAY_REGION = os.environ.get("HOLIDAY_REGION", "BW")  # German state code
SLACK_TIMEOUT = int(os.environ.get("SLACK_API_TIMEOUT", "10"))  # seconds

# Weighted selection parameters
BASE_WEIGHT = 100
YESTERDAY_PENALTY = 50
FREQUENCY_PENALTY_MULTIPLIER = 5  # Penalty per selection in last 30 days
LOOKBACK_DAYS = 30  # Days to look back for frequency calculation
CLEANUP_RETENTION_DAYS = 90  # Keep 90 days of history (3x lookback period)
CLEANUP_PROBABILITY = 0.1  # 10% chance of running cleanup each day


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
    First tries the web service API, then falls back to the holidays library.

    Returns:
        bool: True if today is a public holiday, False otherwise
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
        # Create holidays object for Germany with configurable state
        german_holidays = holidays.Germany(state=HOLIDAY_REGION)
        today = datetime.date.today()
        
        if today in german_holidays:
            holiday_name = german_holidays.get(today)
            logging.info(f"Holiday detected via fallback library ({HOLIDAY_REGION}): {holiday_name}")
            return True
        else:
            logging.debug(f"No holiday today (fallback library, {HOLIDAY_REGION})")
            return False
    except Exception as e:
        logging.error(f"Both holiday checking methods failed: {e}")
        # When in doubt, assume it's not a holiday to avoid missing work days
        return False


def trigger_slack(
    mail: str, max_retries: int = 3, initial_retry_delay: int = 2, dry_run: bool = False
) -> bool:
    """
    Trigger a Slack notification for the specified user.

    Args:
        mail: The email address of the user to be notified
        max_retries: Maximum number of retry attempts
        initial_retry_delay: Initial delay between retries in seconds
        dry_run: If True, skip actual notification sending

    Returns:
        bool: True if notification was successful (or skipped in dry-run), False otherwise
    """
    if not mail:
        logging.error("Cannot trigger Slack notification: mail is None")
        return False

    if dry_run:
        logging.info(f"[DRY RUN] Would send Slack notification to: {mail}")
        return True

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


def cleanup_old_selection_history(conn: sqlite3.Connection, retention_days: int = CLEANUP_RETENTION_DAYS) -> None:
    """
    Clean up old selection history records to prevent unlimited growth.
    
    Args:
        conn: Database connection
        retention_days: Number of days to retain (default: 90 days)
    """
    try:
        cutoff_date = (datetime.date.today() - datetime.timedelta(days=retention_days)).isoformat()
        cursor = conn.cursor()
        
        # Count records that would be deleted
        cursor.execute(
            "SELECT COUNT(*) FROM selection_history WHERE selected_date < ?",
            (cutoff_date,)
        )
        old_count = cursor.fetchone()[0]
        
        if old_count > 0:
            # Delete old records
            cursor.execute(
                "DELETE FROM selection_history WHERE selected_date < ?",
                (cutoff_date,)
            )
            
            deleted_count = cursor.rowcount
            if deleted_count > 0:
                logging.info(f"Cleaned up {deleted_count} old selection history records (older than {retention_days} days)")
        
    except sqlite3.Error as e:
        logging.warning(f"Failed to clean up old selection history: {e}")


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


def get_last_working_day_catcher(conn: sqlite3.Connection) -> Optional[int]:
    """
    Get the user ID of the last working day's catcher (skipping weekends and holidays).

    Args:
        conn: Database connection

    Returns:
        Optional[int]: User ID of the last working day's catcher, or None if no one was selected
    """
    try:
        cursor = conn.cursor()
        
        # Look back up to 7 days to find the last working day with a selection
        for days_back in range(1, 8):
            check_date = datetime.date.today() - datetime.timedelta(days=days_back)
            
            # Skip weekends
            if check_date.weekday() >= 5:  # Saturday or Sunday
                continue
                
            # Check if it was a holiday
            try:
                # Check with holidays library
                german_holidays = holidays.Germany(state=HOLIDAY_REGION)
                if check_date in german_holidays:
                    continue
            except Exception:
                # If holiday check fails, assume it wasn't a holiday
                pass
            
            # Check if someone was selected on this working day
            cursor.execute(
                """
                SELECT user_id 
                FROM selection_history 
                WHERE selected_date = ?
            """,
                (check_date.isoformat(),),
            )
            
            result = cursor.fetchone()
            if result:
                return result[0]
        
        # No catcher found in the last 7 working days
        return None
    except sqlite3.Error as e:
        logging.error(f"Error getting last working day's catcher: {e}")
        return None


def get_recent_selection_count(conn: sqlite3.Connection, user_id: int, days: int = LOOKBACK_DAYS) -> int:
    """
    Get the number of times a user was selected in the last N days.

    Args:
        conn: Database connection
        user_id: User ID to check
        days: Number of days to look back

    Returns:
        int: Number of selections in the specified period
    """
    try:
        cutoff_date = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT COUNT(*) 
            FROM selection_history 
            WHERE user_id = ? 
              AND selected_date >= ?
        """,
            (user_id, cutoff_date),
        )
        
        return cursor.fetchone()[0]
    except sqlite3.Error as e:
        logging.error(f"Error getting recent selection count: {e}")
        return 0


def weighted_random_selection_improved(weighted_users: List[Dict]) -> Dict:
    """
    Improved weighted random selection using cumulative probability.
    More efficient than creating large selection pools.
    
    Args:
        weighted_users: List of dicts with 'user' and 'weight' keys
        
    Returns:
        Selected user dict
    """
    if not weighted_users:
        raise ValueError("No users provided")
    
    if len(weighted_users) == 1:
        return weighted_users[0]["user"]
    
    # Calculate total weight
    total_weight = sum(wu["weight"] for wu in weighted_users)
    
    if total_weight <= 0:
        # All weights are zero or negative - fall back to random selection
        return random.choice(weighted_users)["user"]
    
    # Generate random number between 0 and total_weight
    rand_val = random.uniform(0, total_weight)
    
    # Find the user corresponding to this random value
    cumulative = 0
    for wu in weighted_users:
        cumulative += wu["weight"]
        if rand_val <= cumulative:
            return wu["user"]
    
    # Fallback (shouldn't happen due to floating point precision)
    return weighted_users[-1]["user"]


def add_tie_breaking_logic(weighted_users: List[Dict]) -> List[Dict]:
    """
    Add tie-breaking logic for users with equal weights.
    
    Tie-breaking priority:
    1. User who was selected longest ago (or never selected)
    2. Alphabetical order by email (for deterministic results)
    
    Args:
        weighted_users: List of user weight data
        
    Returns:
        List with tie-breaking weights applied
    """
    # Group users by weight (rounded to avoid floating point issues)
    weight_groups = {}
    for wu in weighted_users:
        # Round to 2 decimal places to group similar weights
        weight_key = round(wu["weight"], 2)
        if weight_key not in weight_groups:
            weight_groups[weight_key] = []
        weight_groups[weight_key].append(wu)
    
    # Apply tie-breaking within each weight group
    result = []
    for weight, users in weight_groups.items():
        if len(users) == 1:
            # No tie to break
            result.extend(users)
        else:
            # Break ties by last_chosen date, then by email
            users_sorted = sorted(users, key=lambda wu: (
                wu["user"]["last_chosen"] or "1900-01-01",  # Never selected = oldest
                wu["user"]["mail"]  # Alphabetical as final tie-breaker
            ))
            
            # Add small incremental bonus to maintain preference order
            for i, wu in enumerate(users_sorted):
                # Add tiny increment to break ties while preserving weight meaning
                tie_breaker = 0.1 / (i + 1)  # 0.1, 0.05, 0.033, etc.
                wu_copy = wu.copy()
                wu_copy["weight"] = wu["weight"] + tie_breaker
                wu_copy["tie_breaker_applied"] = tie_breaker
                result.append(wu_copy)
    
    return result


def calculate_user_weight(
    user_id: int, 
    last_chosen: Optional[str], 
    last_working_day_catcher_id: Optional[int],
    recent_selections: int,
    has_alternatives: bool
) -> float:
    """
    Calculate the selection weight for a user.

    Args:
        user_id: User ID
        last_chosen: Last chosen date (ISO format) or None
        last_working_day_catcher_id: User ID of the last working day's catcher
        recent_selections: Number of recent selections
        has_alternatives: Whether there are other available users

    Returns:
        float: Calculated weight for selection
    """
    weight = BASE_WEIGHT
    
    # Add weight based on days since last selection
    if last_chosen:
        try:
            last_date = datetime.datetime.strptime(last_chosen, "%Y-%m-%d").date()
            days_since = (datetime.date.today() - last_date).days
            weight += days_since
        except ValueError:
            # If date parsing fails, treat as never selected
            weight += 365  # High bonus for never selected
    else:
        # Never selected - give high bonus
        weight += 365
    
    # Apply penalty for being selected on the last working day (only if alternatives exist)
    if has_alternatives and last_working_day_catcher_id == user_id:
        weight -= YESTERDAY_PENALTY
    
    # Apply frequency penalty
    frequency_penalty = recent_selections * FREQUENCY_PENALTY_MULTIPLIER
    weight -= frequency_penalty
    
    return max(weight, 1)  # Ensure weight is always positive


def find_next_catcher_weighted(dry_run: bool = False, debug_weights: bool = False) -> Tuple[Optional[str], bool]:
    """
    Find the next available user using weighted selection algorithm.

    Args:
        dry_run: If True, don't update the database
        debug_weights: If True, show weight calculations for all users

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
                SELECT u.mail 
                FROM user u
                JOIN selection_history sh ON u.id = sh.user_id
                WHERE sh.selected_date = ?
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
                SELECT id, mail, last_chosen
                FROM user 
                WHERE weekdays LIKE ?
            """,
                (f"%{weekday}%",),
            )

            all_users = cur.fetchall()
            
            # Filter out users who are on vacation
            available_users = []
            for user in all_users:
                if not is_user_on_vacation(conn, user["id"], today):
                    available_users.append(user)

            if not available_users:
                logging.warning("No available users found for today (all on vacation or not scheduled)")
                return None, False

            # Get last working day's catcher
            last_working_day_catcher_id = get_last_working_day_catcher(conn)
            
            # Check if we have alternatives to last working day's catcher
            has_alternatives = len(available_users) > 1 or (
                len(available_users) == 1 and available_users[0]["id"] != last_working_day_catcher_id
            )

            # Calculate weights for all available users
            weighted_users = []
            for user in available_users:
                recent_selections = get_recent_selection_count(conn, user["id"])
                weight = calculate_user_weight(
                    user["id"],
                    user["last_chosen"],
                    last_working_day_catcher_id,
                    recent_selections,
                    has_alternatives
                )
                
                weighted_users.append({
                    "user": user,
                    "weight": weight,
                    "recent_selections": recent_selections,
                    "is_yesterday": user["id"] == last_working_day_catcher_id
                })

            # Apply tie-breaking logic for users with equal weights
            weighted_users = add_tie_breaking_logic(weighted_users)
            
            # Sort by final weight (highest first) for debugging
            weighted_users.sort(key=lambda x: x["weight"], reverse=True)

            if debug_weights:
                logging.info("Weight calculations for all eligible users (after tie-breaking):")
                for wu in weighted_users:
                    user = wu["user"]
                    tie_breaker = wu.get("tie_breaker_applied", 0)
                    base_weight = wu["weight"] - tie_breaker if tie_breaker > 0 else wu["weight"]
                    tie_info = f" (base: {base_weight:.1f} + tie_breaker: {tie_breaker:.3f})" if tie_breaker > 0 else ""
                    logging.info(
                        f"  {user['mail']}: weight={wu['weight']:.3f}, "
                        f"last_chosen={user['last_chosen']}, "
                        f"recent_selections={wu['recent_selections']}, "
                        f"is_last_working_day={wu['is_yesterday']}{tie_info}"
                    )

            # Weighted random selection using improved algorithm
            selected_user = weighted_random_selection_improved(weighted_users)

            if dry_run:
                selected_weight = next(wu['weight'] for wu in weighted_users if wu['user']['id'] == selected_user['id'])
                logging.info(f"[DRY RUN] Would select: {selected_user['mail']} (final weight: {selected_weight:.3f})")
            else:
                # Record the selection in history
                cur.execute(
                    "INSERT INTO selection_history (user_id, selected_date) VALUES (?, ?)",
                    (selected_user["id"], today),
                )
                
                # Update the last_chosen date for backward compatibility
                cur.execute(
                    "UPDATE user SET last_chosen = ? WHERE id = ?",
                    (today, selected_user["id"]),
                )
                
                conn.commit()
                
                # Occasionally clean up old selection history (10% chance)
                if not dry_run and random.random() < CLEANUP_PROBABILITY:
                    cleanup_old_selection_history(conn)
                
                selected_weight = next(wu['weight'] for wu in weighted_users if wu['user']['id'] == selected_user['id'])
                logging.info(f"Selected new catcher: {selected_user['mail']} (final weight: {selected_weight:.3f})")

            return selected_user["mail"], True

    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")
        return None, False


def main() -> None:
    """
    Main function to run the Catcher of the Day process.
    """
    try:
        # Parse command line arguments
        args = parse_arguments()
        
        if args.dry_run:
            logging.info("[DRY RUN] Running in dry-run mode - no database changes or notifications will be sent")
        
        # Validate environment variables
        validate_environment()

        # Check if today is a non-working day
        if is_weekend():
            logging.info("Today is a weekend, no catcher needed")
            return

        if is_holiday():
            logging.info("Today is a holiday, no catcher needed")
            return

        # Find next catcher using weighted algorithm
        mail, is_new_selection = find_next_catcher_weighted(
            dry_run=args.dry_run, 
            debug_weights=args.debug_weights
        )
        
        if mail:
            if is_new_selection:
                # Only trigger Slack if this is a new selection
                success = trigger_slack(mail, dry_run=args.dry_run)
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
