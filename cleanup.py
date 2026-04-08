"""Shared cleanup utilities for selection history and vacations."""

import sqlite3
import logging
import datetime

logger = logging.getLogger(__name__)


def cleanup_old_selection_history(
    conn: sqlite3.Connection,
    retention_days: int = 365,
    dry_run: bool = False,
) -> int:
    """
    Delete selection history records older than retention_days.

    Args:
        conn: Database connection
        retention_days: Number of days to retain
        dry_run: If True, only log what would be deleted

    Returns:
        Number of records deleted (or that would be deleted)
    """
    cutoff_date = (
        datetime.date.today() - datetime.timedelta(days=retention_days)
    ).isoformat()

    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM selection_history WHERE selected_date < ?",
            (cutoff_date,),
        )
        count = cursor.fetchone()[0]

        if count == 0:
            return 0

        if dry_run:
            logger.info(
                f"[DRY RUN] Would delete {count} selection history records "
                f"older than {retention_days} days"
            )
            return count

        cursor.execute(
            "DELETE FROM selection_history WHERE selected_date < ?",
            (cutoff_date,),
        )
        deleted = cursor.rowcount
        logger.info(
            f"Cleaned up {deleted} old selection history records "
            f"(older than {retention_days} days)"
        )
        return deleted

    except sqlite3.Error as e:
        logger.warning(f"Failed to clean up old selection history: {e}")
        return 0
