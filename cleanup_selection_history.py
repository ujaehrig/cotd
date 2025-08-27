#!/usr/bin/env python3

"""
Cleanup script for old selection history records.

This script removes selection_history records older than a specified number of days,
keeping only the data needed for the weighted selection algorithm.
"""

import sqlite3
import logging
import argparse
import datetime
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

DATABASE_PATH = "user.db"
DEFAULT_RETENTION_DAYS = 90  # Keep 3 months of history (more than the 30-day lookback)


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Clean up old selection history records"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=DEFAULT_RETENTION_DAYS,
        help=f"Number of days to retain (default: {DEFAULT_RETENTION_DAYS})"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting"
    )
    return parser.parse_args()


def get_db_connection():
    """Create and return a database connection."""
    return sqlite3.connect(DATABASE_PATH)


def cleanup_selection_history(retention_days: int, dry_run: bool = False):
    """
    Clean up old selection history records.
    
    Args:
        retention_days: Number of days to retain
        dry_run: If True, don't actually delete records
    """
    cutoff_date = (datetime.date.today() - datetime.timedelta(days=retention_days)).isoformat()
    
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # First, count how many records would be affected
            cursor.execute(
                "SELECT COUNT(*) FROM selection_history WHERE selected_date < ?",
                (cutoff_date,)
            )
            old_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM selection_history")
            total_count = cursor.fetchone()[0]
            
            if old_count == 0:
                logging.info("No old records to clean up")
                return
            
            logging.info(f"Found {old_count} records older than {retention_days} days (cutoff: {cutoff_date})")
            logging.info(f"Total records: {total_count}, keeping: {total_count - old_count}")
            
            if dry_run:
                logging.info("[DRY RUN] Would delete the old records")
                
                # Show some examples of what would be deleted
                cursor.execute("""
                    SELECT u.mail, sh.selected_date 
                    FROM selection_history sh
                    JOIN user u ON sh.user_id = u.id
                    WHERE sh.selected_date < ?
                    ORDER BY sh.selected_date
                    LIMIT 5
                """, (cutoff_date,))
                
                examples = cursor.fetchall()
                if examples:
                    logging.info("Examples of records that would be deleted:")
                    for mail, date in examples:
                        logging.info(f"  {mail} on {date}")
                    if old_count > 5:
                        logging.info(f"  ... and {old_count - 5} more")
            else:
                # Actually delete the records
                cursor.execute(
                    "DELETE FROM selection_history WHERE selected_date < ?",
                    (cutoff_date,)
                )
                
                deleted_count = cursor.rowcount
                conn.commit()
                
                logging.info(f"Successfully deleted {deleted_count} old selection history records")
                logging.info(f"Retained {total_count - deleted_count} recent records")
                
    except sqlite3.Error as e:
        logging.error(f"Database error during cleanup: {e}")
        raise


def main():
    """Main function."""
    args = parse_arguments()
    
    # Check if database exists
    if not Path(DATABASE_PATH).exists():
        logging.error(f"Database file {DATABASE_PATH} not found")
        return 1
    
    logging.info(f"Cleaning up selection history older than {args.days} days")
    
    try:
        cleanup_selection_history(args.days, args.dry_run)
        logging.info("Cleanup completed successfully")
        return 0
    except Exception as e:
        logging.error(f"Cleanup failed: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
