"""
Cleanup script for old selection history records.

This script removes selection_history records older than a specified number of days,
keeping only the data needed for the weighted selection algorithm.
"""

import argparse
import logging
import os
import sqlite3
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

from dotenv import load_dotenv

from cotd.cleanup import cleanup_old_selection_history
from cotd.db import DATABASE_PATH, get_db_connection

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

DEFAULT_RETENTION_DAYS = int(os.environ.get("CLEANUP_RETENTION_DAYS", "365"))


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Clean up old selection history records"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=DEFAULT_RETENTION_DAYS,
        help=f"Number of days to retain (default: {DEFAULT_RETENTION_DAYS})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting",
    )
    return parser.parse_args()


def main():
    """Main function."""
    args = parse_arguments()

    # Check if database exists
    if not Path(DATABASE_PATH).exists():
        logger.error(f"Database file {DATABASE_PATH} not found")
        return 1

    logger.info(f"Cleaning up selection history older than {args.days} days")

    try:
        with get_db_connection() as conn:
            cleanup_old_selection_history(conn, args.days, args.dry_run)
            if not args.dry_run:
                conn.commit()
        logger.info("Cleanup completed successfully")
        return 0
    except (sqlite3.Error, OSError) as e:
        logger.error(f"Cleanup failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
