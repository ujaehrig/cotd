#!/usr/bin/env -S uv run --script

# /// script
# dependencies = [
#    "icalendar>=7.0.0",
#    "rapidfuzz>=3.0.0",
#    "requests>=2.25.0",
#    "python-dotenv>=1.0.0",
# ]
# ///

"""
Vacation sync module that orchestrates iCal fetching, user matching, and database updates.
"""

import sqlite3
import logging
from datetime import datetime
from typing import Optional, List, Tuple
from dotenv import load_dotenv

from ical_sync import ICalParser
from user_matcher import UserMatcher

load_dotenv()

logger = logging.getLogger(__name__)


class VacationSync:
    """Orchestrates vacation synchronization from iCal feeds."""

    def __init__(self, db_path: str = None):
        """
        Initialize vacation sync.

        Args:
            db_path: Path to database file. If None, uses DB_PATH env var or default.
        """
        if db_path is None:
            from db import DATABASE_PATH
            db_path = DATABASE_PATH
        self.db_path = db_path
        self.parser = ICalParser()
        self.matcher = UserMatcher()

    def get_tenant_users(
        self, 
        conn: sqlite3.Connection, 
        tenant_id: int
    ) -> List[Tuple[int, str, Optional[str]]]:
        """
        Get all users for a tenant.

        Args:
            conn: Database connection
            tenant_id: Tenant ID

        Returns:
            List of (user_id, email, display_name) tuples
        """
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, mail, display_name FROM user WHERE tenant_id = ?",
            (tenant_id,)
        )
        return cursor.fetchall()

    def sync_tenant_vacations(
        self, 
        tenant_id: int, 
        tenant_name: str,
        ical_url: str
    ) -> Tuple[bool, str]:
        """
        Sync vacations for a single tenant.

        Args:
            tenant_id: Tenant ID
            tenant_name: Tenant name (for logging)
            ical_url: iCal feed URL

        Returns:
            Tuple of (success: bool, message: str)
        """
        logger.info(f"Starting vacation sync for tenant '{tenant_name}' (ID: {tenant_id})")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Fetch calendar
            calendar = self.parser.fetch_calendar(ical_url)
            if calendar is None:
                # Try to use cached data
                logger.warning(f"Failed to fetch calendar for '{tenant_name}', using cached data")
                return self._use_cached_data(conn, tenant_id, tenant_name)

            # Extract events
            events = self.parser.extract_events(calendar)
            logger.info(f"Found {len(events)} events in calendar")

            # Get tenant users
            users = self.get_tenant_users(conn, tenant_id)
            if not users:
                msg = f"No users found for tenant '{tenant_name}'"
                logger.warning(msg)
                self._log_sync(conn, tenant_id, "warning", 0, 0, msg)
                conn.commit()
                return True, msg

            # Upsert matched events and track active UIDs
            matched_count = 0
            active_uids = set()
            sync_time = datetime.now()

            for event in events:
                user_id = self.matcher.match_user(event['title'], users)
                if user_id:
                    uid = event['uid']
                    active_uids.add(uid)
                    cursor.execute("""
                        INSERT INTO vacation
                        (user_id, start_date, end_date, source, last_synced, ical_event_uid)
                        VALUES (?, ?, ?, 'ical', ?, ?)
                        ON CONFLICT(user_id, ical_event_uid) DO UPDATE SET
                            start_date = excluded.start_date,
                            end_date = excluded.end_date,
                            last_synced = excluded.last_synced
                    """, (
                        user_id,
                        event['start_date'].isoformat(),
                        event['end_date'].isoformat(),
                        sync_time.isoformat(),
                        uid,
                    ))
                    matched_count += 1
                    logger.debug(f"Matched '{event['title']}' to user {user_id}")

            # Remove stale iCal vacations no longer in the calendar
            tenant_user_ids = [u[0] for u in users]
            if tenant_user_ids:
                placeholders = ','.join('?' * len(tenant_user_ids))
                if active_uids:
                    uid_placeholders = ','.join('?' * len(active_uids))
                    cursor.execute(f"""
                        DELETE FROM vacation
                        WHERE user_id IN ({placeholders})
                        AND source = 'ical'
                        AND ical_event_uid NOT IN ({uid_placeholders})
                    """, tenant_user_ids + list(active_uids))
                else:
                    cursor.execute(f"""
                        DELETE FROM vacation
                        WHERE user_id IN ({placeholders})
                        AND source = 'ical'
                    """, tenant_user_ids)
                stale_count = cursor.rowcount
                if stale_count:
                    logger.info(f"Removed {stale_count} stale iCal vacation entries")

            # Log sync
            self._log_sync(conn, tenant_id, "success", len(events), matched_count, None)
            conn.commit()

            msg = f"Synced {matched_count} vacations from {len(events)} events"
            logger.info(f"Sync completed for '{tenant_name}': {msg}")
            return True, msg

        except Exception as e:
            error_msg = f"Sync failed: {str(e)}"
            logger.error(f"Error syncing tenant '{tenant_name}': {error_msg}")
            self._log_sync(conn, tenant_id, "error", 0, 0, error_msg)
            conn.commit()
            return False, error_msg
        finally:
            conn.close()

    def _use_cached_data(
        self, 
        conn: sqlite3.Connection, 
        tenant_id: int,
        tenant_name: str
    ) -> Tuple[bool, str]:
        """
        Check if cached vacation data exists and is recent.

        Args:
            conn: Database connection
            tenant_id: Tenant ID
            tenant_name: Tenant name

        Returns:
            Tuple of (success: bool, message: str)
        """
        cursor = conn.cursor()
        
        # Check for recent cached data
        cursor.execute("""
            SELECT COUNT(*) FROM vacation v
            JOIN user u ON v.user_id = u.id
            WHERE u.tenant_id = ? AND v.source = 'ical'
            AND v.last_synced IS NOT NULL
        """, (tenant_id,))
        
        cached_count = cursor.fetchone()[0]
        
        if cached_count > 0:
            msg = f"Using {cached_count} cached vacation entries"
            logger.info(f"Tenant '{tenant_name}': {msg}")
            self._log_sync(conn, tenant_id, "cached", 0, cached_count, "Using cached data")
            return True, msg
        else:
            msg = "No cached data available"
            logger.warning(f"Tenant '{tenant_name}': {msg}")
            self._log_sync(conn, tenant_id, "error", 0, 0, msg)
            return False, msg

    def _log_sync(
        self,
        conn: sqlite3.Connection,
        tenant_id: int,
        status: str,
        events_processed: int,
        users_matched: int,
        error_message: Optional[str]
    ) -> None:
        """Log sync operation to database."""
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO vacation_sync_log 
            (tenant_id, status, events_processed, users_matched, error_message)
            VALUES (?, ?, ?, ?, ?)
        """, (tenant_id, status, events_processed, users_matched, error_message))

    def sync_all_tenants(self) -> None:
        """Sync vacations for all tenants with iCal URLs configured."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, name, ical_url 
            FROM tenants 
            WHERE ical_url IS NOT NULL AND ical_url != ''
            AND active = 1
        """)
        
        tenants = cursor.fetchall()
        conn.close()
        
        if not tenants:
            logger.info("No tenants with iCal URLs configured")
            return
        
        logger.info(f"Syncing vacations for {len(tenants)} tenant(s)")
        
        for tenant_id, tenant_name, ical_url in tenants:
            self.sync_tenant_vacations(tenant_id, tenant_name, ical_url)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )
    
    sync = VacationSync()
    sync.sync_all_tenants()
