#!/usr/bin/env -S uv run --script

# /// script
# dependencies = [
#    "requests>=2.25.0",
#    "python-dotenv>=1.0.0",
#    "holidays>=0.34",
#    "icalendar>=7.0.0",
#    "rapidfuzz>=3.0.0"
# ]
# ///

import os
import sys
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

# Import vacation sync
try:
    from vacation_sync import VacationSync
    VACATION_SYNC_AVAILABLE = True
except ImportError:
    VACATION_SYNC_AVAILABLE = False
    logging.warning("vacation_sync module not available, iCal sync disabled")


# Load environment variables from .env file
load_dotenv()

# Configure logging
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(Path(__file__).parent / "catcher.log"),
    ],
)


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
        help="Perform all checks without updating database or sending notifications",
    )
    parser.add_argument(
        "--debug-weights",
        action="store_true",
        help="Show weight calculations for all eligible users",
    )
    parser.add_argument(
        "--force-notify",
        action="store_true",
        help="Send notification even if catcher was already selected today",
    )
    parser.add_argument(
        "--tenant",
        type=str,
        help="Process specific tenant by name (if not specified, processes all active tenants)",
    )
    return parser.parse_args()


# Constants
DATABASE_PATH = os.environ.get("DB_PATH", str(Path(__file__).parent / "user.db"))
HOLIDAY_API_BASE_URL = "https://date.nager.at/Api/v3/IsTodayPublicHoliday/DE"
HOLIDAY_TIMEOUT = int(os.environ.get("HOLIDAY_API_TIMEOUT", "5"))  # seconds
HOLIDAY_REGION = os.environ.get("HOLIDAY_REGION", "BW")  # German state code
SLACK_TIMEOUT = int(os.environ.get("SLACK_API_TIMEOUT", "10"))  # seconds

# Weighted selection parameters
BASE_WEIGHT = 100
FREQUENCY_PENALTY_MULTIPLIER = 5  # Penalty per selection in last 60 days
BALANCE_BONUS_MULTIPLIER = 10  # Bonus for users with fewer total selections
LOOKBACK_DAYS = 60  # Days to look back for frequency calculation
CLEANUP_RETENTION_DAYS = int(
    os.environ.get("CLEANUP_RETENTION_DAYS", "365")
)  # Keep 1 year of history
CLEANUP_PROBABILITY = 0.1  # 10% chance of running cleanup each day
VACATION_RETENTION_DAYS = int(
    os.environ.get("VACATION_RETENTION_DAYS", "90")
)  # Keep 90 days of past vacations


def cleanup_old_vacations(conn: sqlite3.Connection, dry_run: bool = False) -> None:
    """
    Delete vacation entries older than VACATION_RETENTION_DAYS.
    
    Args:
        conn: Database connection
        dry_run: If True, only log what would be deleted
    """
    cutoff_date = (datetime.datetime.now() - datetime.timedelta(days=VACATION_RETENTION_DAYS)).date().isoformat()
    
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM vacation WHERE end_date < ?",
        (cutoff_date,)
    )
    count = cursor.fetchone()[0]
    
    if count > 0:
        if dry_run:
            logging.info(f"[DRY RUN] Would delete {count} vacation entries older than {cutoff_date}")
        else:
            cursor.execute(
                "DELETE FROM vacation WHERE end_date < ?",
                (cutoff_date,)
            )
            conn.commit()
            logging.info(f"Deleted {count} vacation entries older than {cutoff_date}")


def get_tenant_by_name(conn: sqlite3.Connection, name: str) -> Optional[Dict]:
    """
    Get tenant by name.

    Args:
        conn: Database connection
        name: Tenant name

    Returns:
        Tenant dict or None if not found
    """
    cursor = conn.execute(
        "SELECT id, name, location, webhook_url, active, ical_url FROM tenants WHERE name = ?",
        (name,),
    )
    row = cursor.fetchone()
    if row:
        return {
            "id": row[0],
            "name": row[1],
            "location": row[2],
            "webhook_url": row[3],
            "active": row[4],
            "ical_url": row[5],
        }
    return None


def get_active_tenants(conn: sqlite3.Connection) -> List[Dict]:
    """
    Get all active tenants.

    Args:
        conn: Database connection

    Returns:
        List of tenant dicts
    """
    cursor = conn.execute(
        "SELECT id, name, location, webhook_url, active, ical_url FROM tenants WHERE active = 1 ORDER BY id"
    )
    tenants = []
    for row in cursor.fetchall():
        tenants.append(
            {
                "id": row[0],
                "name": row[1],
                "location": row[2],
                "webhook_url": row[3],
                "active": row[4],
                "ical_url": row[5],
            }
        )
    return tenants


def process_tenant(
    conn: sqlite3.Connection,
    tenant: Dict,
    dry_run: bool = False,
    debug_weights: bool = False,
    force_notify: bool = False,
) -> bool:
    """
    Process catcher selection for a single tenant.

    Args:
        conn: Database connection
        tenant: Tenant dict
        dry_run: If True, don't make changes
        debug_weights: If True, show weight calculations
        force_notify: If True, send notification even if already selected

    Returns:
        True if successful, False otherwise
    """
    try:
        logging.info(f"[{tenant['name']}] Starting selection...")

        # Sync vacations from iCal if configured
        if VACATION_SYNC_AVAILABLE and tenant.get('ical_url'):
            logging.info(f"[{tenant['name']}] Syncing vacations from iCal...")
            try:
                sync = VacationSync()
                success, msg = sync.sync_tenant_vacations(
                    tenant['id'], 
                    tenant['name'], 
                    tenant['ical_url']
                )
                if success:
                    logging.info(f"[{tenant['name']}] {msg}")
                else:
                    logging.warning(f"[{tenant['name']}] {msg}")
            except Exception as e:
                logging.error(f"[{tenant['name']}] iCal sync failed: {e}")

        # Check if today is a non-working day
        if is_weekend():
            logging.info(f"[{tenant['name']}] Today is a weekend, no catcher needed")
            return True

        if is_holiday(tenant["location"]):
            logging.info(f"[{tenant['name']}] Today is a holiday, no catcher needed")
            return True

        # Find next catcher using weighted algorithm
        mail, is_new_selection = find_next_catcher(
            conn=conn,
            tenant_id=tenant["id"],
            dry_run=dry_run,
            debug_weights=debug_weights,
        )

        if mail:
            if is_new_selection or force_notify:
                # Trigger Slack if this is a new selection or force-notify is enabled
                success = trigger_slack(
                    mail, webhook_url=tenant["webhook_url"], dry_run=dry_run
                )
                if success:
                    logging.info(
                        f"[{tenant['name']}] Successfully notified catcher: {mail}"
                    )
                else:
                    logging.error(
                        f"[{tenant['name']}] Failed to notify catcher: {mail}"
                    )
            else:
                logging.info(
                    f"[{tenant['name']}] Using previously selected catcher: {mail}"
                )
            return True
        else:
            logging.warning(f"[{tenant['name']}] No catcher found for today")
            return False

    except Exception as e:
        logging.error(f"[{tenant['name']}] Error processing tenant: {e}", exc_info=True)
        return False


def is_weekend() -> bool:
    """
    Check if today is a weekend (Saturday or Sunday).

    Returns:
        bool: True if today is a weekend, False otherwise
    """
    return datetime.datetime.now().weekday() >= 5  # 5 = Saturday, 6 = Sunday


def is_holiday(location: str = None) -> bool:
    """
    Check if today is a public holiday in Germany.
    First tries the web service API, then falls back to the holidays library.

    Args:
        location: German state code (e.g., 'BW', 'BY'). If None, uses HOLIDAY_REGION env var.

    Returns:
        bool: True if today is a public holiday, False otherwise
    """
    if location is None:
        location = HOLIDAY_REGION

    # First try the web service
    try:
        url = f"{HOLIDAY_API_BASE_URL}?countyCode=DE-{location}"
        response = requests.get(url, timeout=HOLIDAY_TIMEOUT)
        if response.status_code == 200:
            logging.info("Holiday detected via web service")
            return True
        elif response.status_code == 204:
            # 204 typically means "no holiday today"
            logging.debug("No holiday today (web service)")
            return False
        else:
            logging.warning(
                f"Web service returned unexpected status: {response.status_code}"
            )
    except requests.exceptions.RequestException as e:
        logging.warning(f"Web service failed, falling back to holidays library: {e}")

    # Fallback to holidays library
    try:
        # Create holidays object for Germany with specified subdivision
        german_holidays = holidays.Germany(subdiv=location)
        today = datetime.date.today()

        if today in german_holidays:
            holiday_name = german_holidays.get(today)
            logging.info(
                f"Holiday detected via fallback library ({location}): {holiday_name}"
            )
            return True
        else:
            logging.debug(f"No holiday today (fallback library, {location})")
            return False
    except Exception as e:
        logging.error(f"Both holiday checking methods failed: {e}")
        # When in doubt, assume it's not a holiday to avoid missing work days
        return False


def trigger_slack(
    mail: str,
    webhook_url: str,
    max_retries: int = 3,
    initial_retry_delay: int = 2,
    dry_run: bool = False,
) -> bool:
    """
    Trigger a Slack notification for the specified user.

    Args:
        mail: The email address of the user to be notified
        webhook_url: Slack webhook URL (configured per tenant)
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

    if not webhook_url:
        logging.error("No webhook URL configured for tenant")
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


def cleanup_old_selection_history(
    conn: sqlite3.Connection, retention_days: int = CLEANUP_RETENTION_DAYS
) -> None:
    """
    Clean up old selection history records to prevent unlimited growth.

    Args:
        conn: Database connection
        retention_days: Number of days to retain (default: 90 days)
    """
    try:
        cutoff_date = (
            datetime.date.today() - datetime.timedelta(days=retention_days)
        ).isoformat()
        cursor = conn.cursor()

        # Count records that would be deleted
        cursor.execute(
            "SELECT COUNT(*) FROM selection_history WHERE selected_date < ?",
            (cutoff_date,),
        )
        old_count = cursor.fetchone()[0]

        if old_count > 0:
            # Delete old records
            cursor.execute(
                "DELETE FROM selection_history WHERE selected_date < ?", (cutoff_date,)
            )

            deleted_count = cursor.rowcount
            if deleted_count > 0:
                logging.info(
                    f"Cleaned up {deleted_count} old selection history records (older than {retention_days} days)"
                )

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
                german_holidays = holidays.Germany(subdiv=HOLIDAY_REGION)
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


def get_recent_selection_count(
    conn: sqlite3.Connection, user_id: int, days: int = LOOKBACK_DAYS
) -> int:
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
        cutoff_date = (
            datetime.date.today() - datetime.timedelta(days=days)
        ).isoformat()
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
        logging.warning("All weights are zero or negative, using random selection")
        return random.choice(weighted_users)["user"]

    # Generate random number between 0 and total_weight (exclusive)
    rand_val = random.random() * total_weight

    # Debug logging
    logging.debug(f"Random value: {rand_val:.3f}, Total weight: {total_weight:.3f}")

    # Find the user corresponding to this random value
    cumulative = 0
    for i, wu in enumerate(weighted_users):
        cumulative += wu["weight"]
        logging.debug(
            f"User {i}: {wu['user']['mail']}, weight: {wu['weight']:.3f}, cumulative: {cumulative:.3f}"
        )
        if rand_val < cumulative:
            logging.debug(
                f"Selected user {wu['user']['mail']} (rand_val {rand_val:.3f} < cumulative {cumulative:.3f})"
            )
            return wu["user"]

    # Fallback (shouldn't happen due to floating point precision)
    logging.warning("Fallback selection used - this shouldn't happen")
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
            users_sorted = sorted(
                users,
                key=lambda wu: (
                    wu["user"]["last_chosen"]
                    or "1900-01-01",  # Never selected = oldest
                    wu["user"]["mail"],  # Alphabetical as final tie-breaker
                ),
            )

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
    total_selections: int,
    avg_total_selections: float,
    has_alternatives: bool,
) -> float:
    """
    Calculate the selection weight for a user.

    Args:
        user_id: User ID
        last_chosen: Last chosen date (ISO format) or None
        last_working_day_catcher_id: User ID of the last working day's catcher
        recent_selections: Number of recent selections
        total_selections: Total number of selections (all time)
        avg_total_selections: Average total selections across all users
        has_alternatives: Whether there are other available users

    Returns:
        float: Calculated weight for selection
    """
    weight = BASE_WEIGHT

    # Add weight based on days since last selection (non-linear growth)
    if last_chosen:
        try:
            last_date = datetime.datetime.strptime(last_chosen, "%Y-%m-%d").date()
            days_since = (datetime.date.today() - last_date).days
            # Use square root for gradual acceleration, then square for stronger acceleration after 10 days
            if days_since <= 10:
                weight += days_since**1.2  # Slight acceleration
            else:
                weight += (10**1.2) + (
                    (days_since - 10) ** 1.5
                )  # Stronger acceleration
        except ValueError:
            # If date parsing fails, treat as never selected
            weight += 500  # High bonus for never selected
    else:
        # Never selected - give high bonus
        weight += 500

    # Apply penalty for being selected on the last working day (only if alternatives exist)
    if has_alternatives and last_working_day_catcher_id == user_id:
        # Make the penalty much more aggressive - reduce weight to a very small fraction
        weight = max(weight * 0.1, 1)  # Reduce to 10% of original weight, minimum 1
        logging.debug(
            f"Applied consecutive day penalty to user {user_id}: weight reduced to {weight:.3f}"
        )

    # Apply frequency penalty
    frequency_penalty = recent_selections * FREQUENCY_PENALTY_MULTIPLIER
    weight -= frequency_penalty

    # Apply balance bonus for users with fewer total selections
    if avg_total_selections > 0:
        balance_factor = (
            avg_total_selections - total_selections
        ) / avg_total_selections
        balance_bonus = balance_factor * BALANCE_BONUS_MULTIPLIER
        weight += balance_bonus

    return max(weight, 1)  # Ensure weight is always positive


def find_next_catcher(
    conn: sqlite3.Connection = None,
    tenant_id: int = None,
    dry_run: bool = False,
    debug_weights: bool = False,
) -> Tuple[Optional[str], bool]:
    """
    Find the next available user using weighted selection algorithm.

    Args:
        conn: Database connection (if None, creates new connection)
        tenant_id: Tenant ID to filter users by
        dry_run: If True, don't update the database
        debug_weights: If True, show weight calculations for all users

    Returns:
        Tuple[Optional[str], bool]: A tuple containing:
            - The email address of the next available user or None
            - Boolean indicating if a new user was selected (True) or if we're using a previously selected user (False)
    """
    try:
        if conn is None:
            conn = get_db_connection()
            should_close = True
        else:
            should_close = False
            # Ensure row_factory is set
            if conn.row_factory is None:
                conn.row_factory = sqlite3.Row

        try:
            cur = conn.cursor()
            today = datetime.date.today().isoformat()

            # Check if someone is already chosen for today (filtered by tenant)
            if tenant_id:
                cur.execute(
                    """
                    SELECT u.mail 
                    FROM user u
                    JOIN selection_history sh ON u.id = sh.user_id
                    WHERE sh.selected_date = ? AND u.tenant_id = ?
                """,
                    (today, tenant_id),
                )
            else:
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

            # Get current weekday (strftime %w: 0=Sunday, 1=Monday, ..., 6=Saturday)
            weekday = datetime.datetime.now().strftime("%w")

            # Get all users who are available on this weekday (filtered by tenant)
            if tenant_id:
                cur.execute(
                    """
                    SELECT id, mail, last_chosen
                    FROM user 
                    WHERE weekdays LIKE ? AND tenant_id = ?
                """,
                    (f"%{weekday}%", tenant_id),
                )
            else:
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
                logging.warning(
                    "No available users found for today (all on vacation or not scheduled)"
                )
                return None, False

            # Get last working day's catcher
            last_working_day_catcher_id = get_last_working_day_catcher(conn)

            # Check if we have alternatives to last working day's catcher
            has_alternatives = len(available_users) > 1 or (
                len(available_users) == 1
                and available_users[0]["id"] != last_working_day_catcher_id
            )

            # Calculate weights for all available users
            weighted_users = []

            # Get total selection counts for balance calculation
            total_selections_map = {}
            for user in available_users:
                cur.execute(
                    "SELECT COUNT(*) FROM selection_history WHERE user_id = ?",
                    (user["id"],),
                )
                total_selections_map[user["id"]] = cur.fetchone()[0]

            # Calculate average total selections
            avg_total_selections = (
                sum(total_selections_map.values()) / len(total_selections_map)
                if total_selections_map
                else 0
            )

            for user in available_users:
                recent_selections = get_recent_selection_count(conn, user["id"])
                total_selections = total_selections_map[user["id"]]
                weight = calculate_user_weight(
                    user["id"],
                    user["last_chosen"],
                    last_working_day_catcher_id,
                    recent_selections,
                    total_selections,
                    avg_total_selections,
                    has_alternatives,
                )

                weighted_users.append(
                    {
                        "user": user,
                        "weight": weight,
                        "recent_selections": recent_selections,
                        "total_selections": total_selections,
                        "is_yesterday": user["id"] == last_working_day_catcher_id,
                    }
                )

            # Apply tie-breaking logic for users with equal weights
            weighted_users = add_tie_breaking_logic(weighted_users)

            # Sort by final weight (highest first) for debugging
            weighted_users.sort(key=lambda x: x["weight"], reverse=True)

            if debug_weights:
                total_weight = sum(wu["weight"] for wu in weighted_users)
                logging.info(
                    "Weight calculations for all eligible users (after tie-breaking):"
                )
                for wu in weighted_users:
                    user = wu["user"]
                    tie_breaker = wu.get("tie_breaker_applied", 0)
                    base_weight = (
                        wu["weight"] - tie_breaker if tie_breaker > 0 else wu["weight"]
                    )
                    tie_info = (
                        f" (base: {base_weight:.1f} + tie_breaker: {tie_breaker:.3f})"
                        if tie_breaker > 0
                        else ""
                    )
                    probability = (
                        (wu["weight"] / total_weight) * 100 if total_weight > 0 else 0
                    )
                    logging.info(
                        f"  {user['mail']}: weight={wu['weight']:.3f}, "
                        f"probability={probability:.1f}%, "
                        f"last_chosen={user['last_chosen']}, "
                        f"recent_selections={wu['recent_selections']}, "
                        f"total_selections={wu['total_selections']}, "
                        f"is_last_working_day={wu['is_yesterday']}{tie_info}"
                    )

            # Weighted random selection using improved algorithm
            selected_user = weighted_random_selection_improved(weighted_users)

            if dry_run:
                selected_weight = next(
                    wu["weight"]
                    for wu in weighted_users
                    if wu["user"]["id"] == selected_user["id"]
                )
                logging.info(
                    f"[DRY RUN] Would select: {selected_user['mail']} (final weight: {selected_weight:.3f})"
                )
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

                selected_weight = next(
                    wu["weight"]
                    for wu in weighted_users
                    if wu["user"]["id"] == selected_user["id"]
                )
                logging.info(
                    f"Selected new catcher: {selected_user['mail']} (final weight: {selected_weight:.3f})"
                )

            return selected_user["mail"], True

        finally:
            if should_close and conn:
                conn.close()

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
            logging.info(
                "[DRY RUN] Running in dry-run mode - no database changes or notifications will be sent"
            )

        # Connect to database
        conn = sqlite3.connect(DATABASE_PATH)

        try:
            # Cleanup old vacations
            cleanup_old_vacations(conn, args.dry_run)
            
            # Determine which tenants to process
            if args.tenant:
                # Process specific tenant
                tenant = get_tenant_by_name(conn, args.tenant)
                if not tenant:
                    logging.error(f"Tenant '{args.tenant}' not found")
                    sys.exit(1)
                if not tenant["active"]:
                    logging.error(f"Tenant '{args.tenant}' is inactive")
                    sys.exit(1)

                tenants_to_process = [tenant]
            else:
                # Process all active tenants
                tenants_to_process = get_active_tenants(conn)
                if not tenants_to_process:
                    logging.warning("No active tenants found")
                    return

                logging.info(f"Processing {len(tenants_to_process)} active tenants")

            # Process each tenant
            success_count = 0
            for tenant in tenants_to_process:
                if process_tenant(
                    conn, tenant, args.dry_run, args.debug_weights, args.force_notify
                ):
                    success_count += 1

            # Log summary for multiple tenants
            if len(tenants_to_process) > 1:
                logging.info(
                    f"Completed {success_count}/{len(tenants_to_process)} tenants successfully"
                )

        finally:
            conn.close()

    except Exception as e:
        logging.error(f"Unexpected error: {e}", exc_info=True)


if __name__ == "__main__":
    main()
