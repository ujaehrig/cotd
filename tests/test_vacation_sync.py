"""Tests for vacation_sync.py - vacation synchronization orchestration."""

import sqlite3
import pytest
from datetime import date
from pathlib import Path
from unittest.mock import patch, MagicMock

from vacation_sync import VacationSync


@pytest.fixture
def db_path(tmp_path):
    """Create a test database with all required tables."""
    path = tmp_path / "test.db"
    conn = sqlite3.connect(path)

    schema_path = Path(__file__).parent.parent / "schema_tenants.sql"
    conn.executescript(schema_path.read_text())

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS user (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mail VARCHAR(50) UNIQUE NOT NULL,
            weekdays VARCHAR(10),
            last_chosen DATE,
            tenant_id INTEGER REFERENCES tenants(id),
            display_name VARCHAR(100)
        );
        CREATE TABLE IF NOT EXISTS vacation (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            start_date DATE NOT NULL,
            end_date DATE NOT NULL,
            source VARCHAR(20) DEFAULT 'manual',
            last_synced TIMESTAMP,
            ical_event_uid VARCHAR(200),
            FOREIGN KEY (user_id) REFERENCES user(id),
            UNIQUE (user_id, ical_event_uid)
        );
        CREATE TABLE IF NOT EXISTS vacation_sync_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER NOT NULL,
            sync_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status VARCHAR(20),
            events_processed INTEGER DEFAULT 0,
            users_matched INTEGER DEFAULT 0,
            error_message TEXT,
            FOREIGN KEY (tenant_id) REFERENCES tenants(id)
        );
    """)

    # Seed data
    conn.execute(
        "INSERT INTO tenants (name, location, webhook_url, active, ical_url) VALUES (?, ?, ?, ?, ?)",
        ("Team Alpha", "BW", "https://hooks.example.com/alpha", 1, "https://cal.example.com/alpha.ics"),
    )
    conn.execute(
        "INSERT INTO tenants (name, location, webhook_url, active) VALUES (?, ?, ?, ?)",
        ("Team NoICal", "BY", "https://hooks.example.com/noical", 1),
    )
    conn.execute(
        "INSERT INTO user (mail, weekdays, tenant_id, display_name) VALUES (?, ?, ?, ?)",
        ("alice@example.com", "1,2,3,4,5", 1, "Alice Wonder"),
    )
    conn.execute(
        "INSERT INTO user (mail, weekdays, tenant_id) VALUES (?, ?, ?)",
        ("bob@example.com", "1,2,3,4,5", 1),
    )
    conn.commit()
    conn.close()
    return str(path)


@pytest.fixture
def sync(db_path):
    return VacationSync(db_path=db_path)


class TestGetTenantUsers:
    def test_returns_users_for_tenant(self, sync, db_path):
        conn = sqlite3.connect(db_path)
        users = sync.get_tenant_users(conn, 1)
        conn.close()
        assert len(users) == 2
        emails = [u[1] for u in users]
        assert "alice@example.com" in emails

    def test_empty_for_unknown_tenant(self, sync, db_path):
        conn = sqlite3.connect(db_path)
        users = sync.get_tenant_users(conn, 999)
        conn.close()
        assert users == []


class TestSyncTenantVacations:
    @patch.object(VacationSync, "__init__", lambda self, **kw: None)
    def _make_sync(self, db_path):
        s = VacationSync.__new__(VacationSync)
        s.db_path = db_path
        s.parser = MagicMock()
        s.matcher = MagicMock()
        return s

    def test_successful_sync(self, db_path):
        s = self._make_sync(db_path)
        from icalendar import Calendar

        s.parser.fetch_calendar.return_value = Calendar()
        s.parser.extract_events.return_value = [
            {"title": "Alice Wonder", "start_date": date(2026, 7, 1), "end_date": date(2026, 7, 5), "uid": "ev1"},
        ]
        s.matcher.match_user.return_value = 1  # alice

        success, msg = s.sync_tenant_vacations(1, "Team Alpha", "https://cal.example.com/alpha.ics")
        assert success is True
        assert "1" in msg  # matched 1 vacation

        # Verify vacation was inserted
        conn = sqlite3.connect(db_path)
        count = conn.execute("SELECT COUNT(*) FROM vacation WHERE source = 'ical'").fetchone()[0]
        conn.close()
        assert count == 1

    def test_no_users_for_tenant(self, db_path):
        s = self._make_sync(db_path)
        from icalendar import Calendar

        s.parser.fetch_calendar.return_value = Calendar()
        s.parser.extract_events.return_value = []

        # Use tenant_id=999 which has no users
        success, msg = s.sync_tenant_vacations(999, "Empty Team", "https://cal.example.com/empty.ics")
        assert success is True
        assert "No users" in msg

    def test_calendar_fetch_failure_uses_cache(self, db_path):
        s = self._make_sync(db_path)
        s.parser.fetch_calendar.return_value = None

        success, msg = s.sync_tenant_vacations(1, "Team Alpha", "https://cal.example.com/alpha.ics")
        # No cached data exists, so should report failure
        assert success is False
        assert "cached" in msg.lower() or "No cached" in msg

    def test_unmatched_events_skipped(self, db_path):
        s = self._make_sync(db_path)
        from icalendar import Calendar

        s.parser.fetch_calendar.return_value = Calendar()
        s.parser.extract_events.return_value = [
            {"title": "Unknown Person", "start_date": date(2026, 7, 1), "end_date": date(2026, 7, 5), "uid": "ev1"},
        ]
        s.matcher.match_user.return_value = None

        success, msg = s.sync_tenant_vacations(1, "Team Alpha", "https://cal.example.com/alpha.ics")
        assert success is True
        assert "0" in msg  # 0 matched

    def test_exception_during_sync(self, db_path):
        s = self._make_sync(db_path)
        s.parser.fetch_calendar.side_effect = Exception("DB exploded")

        success, msg = s.sync_tenant_vacations(1, "Team Alpha", "https://cal.example.com/alpha.ics")
        assert success is False
        assert "failed" in msg.lower()

    def test_upsert_updates_existing_event(self, db_path):
        """Running sync twice with same UID updates rather than duplicates."""
        s = self._make_sync(db_path)
        from icalendar import Calendar

        s.parser.fetch_calendar.return_value = Calendar()
        s.parser.extract_events.return_value = [
            {"title": "Alice Wonder", "start_date": date(2026, 7, 1), "end_date": date(2026, 7, 5), "uid": "ev1"},
        ]
        s.matcher.match_user.return_value = 1

        s.sync_tenant_vacations(1, "Team Alpha", "https://cal.example.com/alpha.ics")

        # Sync again with updated dates
        s.parser.extract_events.return_value = [
            {"title": "Alice Wonder", "start_date": date(2026, 7, 2), "end_date": date(2026, 7, 6), "uid": "ev1"},
        ]
        s.sync_tenant_vacations(1, "Team Alpha", "https://cal.example.com/alpha.ics")

        conn = sqlite3.connect(db_path)
        rows = conn.execute(
            "SELECT start_date, end_date FROM vacation WHERE source = 'ical'"
        ).fetchall()
        conn.close()
        assert len(rows) == 1
        assert rows[0][0] == "2026-07-02"
        assert rows[0][1] == "2026-07-06"

    def test_removed_event_is_deleted(self, db_path):
        """Events removed from calendar are deleted from DB."""
        s = self._make_sync(db_path)
        from icalendar import Calendar

        s.parser.fetch_calendar.return_value = Calendar()
        s.parser.extract_events.return_value = [
            {"title": "Alice", "start_date": date(2026, 7, 1), "end_date": date(2026, 7, 5), "uid": "ev1"},
            {"title": "Alice", "start_date": date(2026, 8, 1), "end_date": date(2026, 8, 5), "uid": "ev2"},
        ]
        s.matcher.match_user.return_value = 1

        s.sync_tenant_vacations(1, "Team Alpha", "https://cal.example.com/alpha.ics")

        # Second sync with ev2 removed
        s.parser.extract_events.return_value = [
            {"title": "Alice", "start_date": date(2026, 7, 1), "end_date": date(2026, 7, 5), "uid": "ev1"},
        ]
        s.sync_tenant_vacations(1, "Team Alpha", "https://cal.example.com/alpha.ics")

        conn = sqlite3.connect(db_path)
        count = conn.execute("SELECT COUNT(*) FROM vacation WHERE source = 'ical'").fetchone()[0]
        conn.close()
        assert count == 1

    def test_manual_vacations_untouched(self, db_path):
        """Manual vacations are not affected by iCal sync."""
        conn = sqlite3.connect(db_path)
        conn.execute(
            "INSERT INTO vacation (user_id, start_date, end_date, source) VALUES (1, '2026-09-01', '2026-09-05', 'manual')"
        )
        conn.commit()
        conn.close()

        s = self._make_sync(db_path)
        from icalendar import Calendar

        s.parser.fetch_calendar.return_value = Calendar()
        s.parser.extract_events.return_value = [
            {"title": "Alice", "start_date": date(2026, 7, 1), "end_date": date(2026, 7, 5), "uid": "ev1"},
        ]
        s.matcher.match_user.return_value = 1

        s.sync_tenant_vacations(1, "Team Alpha", "https://cal.example.com/alpha.ics")

        conn = sqlite3.connect(db_path)
        manual = conn.execute("SELECT COUNT(*) FROM vacation WHERE source = 'manual'").fetchone()[0]
        ical = conn.execute("SELECT COUNT(*) FROM vacation WHERE source = 'ical'").fetchone()[0]
        conn.close()
        assert manual == 1
        assert ical == 1


class TestUseCachedData:
    def test_with_cached_entries(self, db_path):
        # Insert cached ical vacation
        conn = sqlite3.connect(db_path)
        conn.execute(
            "INSERT INTO vacation (user_id, start_date, end_date, source, last_synced) VALUES (1, '2026-07-01', '2026-07-05', 'ical', '2026-04-01T00:00:00')"
        )
        conn.commit()
        conn.close()

        s = VacationSync(db_path=db_path)
        conn = sqlite3.connect(db_path)
        success, msg = s._use_cached_data(conn, 1, "Team Alpha")
        conn.close()
        assert success is True
        assert "cached" in msg.lower()

    def test_without_cached_entries(self, db_path):
        s = VacationSync(db_path=db_path)
        conn = sqlite3.connect(db_path)
        success, msg = s._use_cached_data(conn, 1, "Team Alpha")
        conn.close()
        assert success is False


class TestSyncAllTenants:
    @patch.object(VacationSync, "sync_tenant_vacations")
    def test_syncs_tenants_with_ical_url(self, mock_sync, db_path):
        mock_sync.return_value = (True, "ok")
        s = VacationSync(db_path=db_path)
        s.sync_all_tenants()
        # Only Team Alpha has ical_url
        assert mock_sync.call_count == 1
        assert mock_sync.call_args[0][1] == "Team Alpha"

    @patch.object(VacationSync, "sync_tenant_vacations")
    def test_skips_tenants_without_ical_url(self, mock_sync, db_path):
        # Remove ical_url from all tenants
        conn = sqlite3.connect(db_path)
        conn.execute("UPDATE tenants SET ical_url = NULL")
        conn.commit()
        conn.close()

        s = VacationSync(db_path=db_path)
        s.sync_all_tenants()
        assert mock_sync.call_count == 0
