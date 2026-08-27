"""Tests for vacation lookahead bonus feature.

The vacation lookahead bonus gives users with upcoming vacation a weight
boost so they get selected more often *before* they leave, rather than
in a burst after they return.
"""

import datetime
import logging
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest
from freezegun import freeze_time

from catcher import (
    LOOKAHEAD_DAYS,
    VACATION_LOOKAHEAD_BONUS,
    calculate_user_weight,
    find_next_catcher,
    get_upcoming_vacation_working_days,
)


@pytest.fixture
def db(tmp_path):
    """Create a fully-populated test database."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    schema_path = Path(__file__).parent.parent / "schema_tenants.sql"
    conn.executescript(schema_path.read_text())

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS user (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mail VARCHAR(50) UNIQUE NOT NULL,
            weekdays VARCHAR(10),
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
            FOREIGN KEY (user_id) REFERENCES user(id)
        );
        CREATE TABLE IF NOT EXISTS selection_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            selected_date DATE NOT NULL,
            tenant_id INTEGER NOT NULL,
            FOREIGN KEY (user_id) REFERENCES user(id),
            FOREIGN KEY (tenant_id) REFERENCES tenants(id)
        );
    """)

    # Seed tenants
    conn.execute(
        "INSERT INTO tenants (name, location, webhook_url, active) VALUES (?, ?, ?, ?)",
        ("Team Alpha", "BW", "https://hooks.example.com/alpha", 1),
    )

    # Seed users for Team Alpha (tenant_id=1)
    conn.execute(
        "INSERT INTO user (mail, weekdays, tenant_id) VALUES (?, ?, ?)",
        ("alice@example.com", "1,2,3,4,5", 1),
    )
    conn.execute(
        "INSERT INTO user (mail, weekdays, tenant_id) VALUES (?, ?, ?)",
        ("bob@example.com", "1,2,3,4,5", 1),
    )
    conn.commit()
    yield conn
    conn.close()


# --- Constants ---


class TestConstants:
    def test_lookahead_days_default(self):
        assert LOOKAHEAD_DAYS == 7

    def test_vacation_lookahead_bonus_default(self):
        assert VACATION_LOOKAHEAD_BONUS == 5


# --- get_upcoming_vacation_working_days ---


class TestGetUpcomingVacationWorkingDays:
    def test_no_vacation_returns_zero(self, db):
        result = get_upcoming_vacation_working_days(db, 1)
        assert result == 0

    @freeze_time("2026-09-07")  # Monday
    def test_vacation_starting_tomorrow(self, db):
        """A vacation starting tomorrow should count working days."""
        # Vacation Tue Sep 8 - Fri Sep 11 = 4 working days
        db.execute(
            "INSERT INTO vacation (user_id, start_date, end_date) "
            "VALUES (1, '2026-09-08', '2026-09-11')",
        )
        db.commit()

        result = get_upcoming_vacation_working_days(db, 1)
        assert result == 4  # Tue, Wed, Thu, Fri

    @freeze_time("2026-09-07")  # Monday
    def test_today_excluded(self, db):
        """Today's vacation should NOT be counted (already handled by exclusion)."""
        db.execute(
            "INSERT INTO vacation (user_id, start_date, end_date) "
            "VALUES (1, '2026-09-07', '2026-09-07')",
        )
        db.commit()

        result = get_upcoming_vacation_working_days(db, 1)
        assert result == 0

    @freeze_time("2026-09-09")  # Wednesday
    def test_weekends_excluded(self, db):
        """Weekend days in a vacation should not count."""
        # Window: Sep 10 (Thu) through Sep 16 (Wed) = 7 calendar days
        # Vacation Sep 10-14: Thu(10), Fri(11), Sat(12), Sun(13), Mon(14)
        # Working days in window: Thu, Fri, Mon = 3
        db.execute(
            "INSERT INTO vacation (user_id, start_date, end_date) "
            "VALUES (1, '2026-09-10', '2026-09-14')",
        )
        db.commit()

        result = get_upcoming_vacation_working_days(db, 1)
        assert result == 3  # Thu, Fri, Mon (Sat+Sun excluded)

    @freeze_time("2026-09-07")  # Monday
    def test_holidays_excluded(self, db):
        """Holidays within a vacation should not count as missed working days."""
        # Vacation Tue-Fri (Sep 8-11), but Wed Sep 9 is a holiday
        db.execute(
            "INSERT INTO vacation (user_id, start_date, end_date) "
            "VALUES (1, '2026-09-08', '2026-09-11')",
        )
        db.commit()

        with patch("catcher.holidays.country_holidays") as mock_holidays:
            holiday_set = {datetime.date(2026, 9, 9)}
            mock_holidays.return_value = holiday_set
            result = get_upcoming_vacation_working_days(db, 1)

        assert result == 3  # Tue, Thu, Fri (Wed is holiday)

    @freeze_time("2026-09-07")  # Monday
    def test_only_within_lookahead_window(self, db):
        """Only vacation days within LOOKAHEAD_DAYS should count."""
        # Window: Sep 8 (Tue) through Sep 14 (Mon)
        # Vacation: Sep 12 (Sat) through Oct 2
        # Working days in window from vacation: Mon Sep 14 only
        db.execute(
            "INSERT INTO vacation (user_id, start_date, end_date) "
            "VALUES (1, '2026-09-12', '2026-10-02')",
        )
        db.commit()

        result = get_upcoming_vacation_working_days(db, 1)
        assert result == 1  # Only Mon Sep 14

    @freeze_time("2026-09-07")  # Monday
    def test_vacation_entirely_beyond_window(self, db):
        """Vacation starting after the lookahead window should not count."""
        # Window: Sep 8 through Sep 14
        # Vacation starts Sep 21
        db.execute(
            "INSERT INTO vacation (user_id, start_date, end_date) "
            "VALUES (1, '2026-09-21', '2026-09-25')",
        )
        db.commit()

        result = get_upcoming_vacation_working_days(db, 1)
        assert result == 0

    @freeze_time("2026-09-07")  # Monday
    def test_multiple_vacation_entries(self, db):
        """Multiple non-overlapping vacation entries should all count."""
        # Window: Sep 8 (Tue) through Sep 14 (Mon)
        # Vacation 1: Tue Sep 8
        # Vacation 2: Thu Sep 10 - Fri Sep 11
        db.execute(
            "INSERT INTO vacation (user_id, start_date, end_date) "
            "VALUES (1, '2026-09-08', '2026-09-08')",
        )
        db.execute(
            "INSERT INTO vacation (user_id, start_date, end_date) "
            "VALUES (1, '2026-09-10', '2026-09-11')",
        )
        db.commit()

        result = get_upcoming_vacation_working_days(db, 1)
        assert result == 3  # Tue, Thu, Fri

    @freeze_time("2026-09-07")  # Monday
    def test_ical_and_manual_treated_equally(self, db):
        """Both ical and manual vacation sources should count."""
        # Window: Sep 8 (Tue) through Sep 14 (Mon)
        db.execute(
            "INSERT INTO vacation (user_id, start_date, end_date, source) "
            "VALUES (1, '2026-09-08', '2026-09-08', 'manual')",
        )
        db.execute(
            "INSERT INTO vacation (user_id, start_date, end_date, source) "
            "VALUES (1, '2026-09-10', '2026-09-10', 'ical')",
        )
        db.commit()

        result = get_upcoming_vacation_working_days(db, 1)
        assert result == 2  # Tue + Thu

    @freeze_time("2026-09-07")  # Monday
    def test_custom_lookahead_days(self, db):
        """Custom lookahead_days parameter should be respected."""
        # With lookahead=3: window Sep 8 (Tue) through Sep 10 (Thu)
        # Vacation: entire next week Sep 8-14
        # Working days in 3-day window: Tue, Wed, Thu = 3
        db.execute(
            "INSERT INTO vacation (user_id, start_date, end_date) "
            "VALUES (1, '2026-09-08', '2026-09-14')",
        )
        db.commit()

        result = get_upcoming_vacation_working_days(db, 1, lookahead_days=3)
        assert result == 3  # Tue, Wed, Thu

    @freeze_time("2026-09-07")  # Monday
    def test_different_user_not_affected(self, db):
        """Vacation for user 1 should not affect user 2."""
        db.execute(
            "INSERT INTO vacation (user_id, start_date, end_date) "
            "VALUES (1, '2026-09-08', '2026-09-12')",
        )
        db.commit()

        result = get_upcoming_vacation_working_days(db, 2)
        assert result == 0

    def test_db_error_returns_zero(self, db):
        """Database errors should be handled gracefully, returning 0."""
        db.close()
        conn = sqlite3.connect(":memory:")  # Empty DB, no vacation table
        result = get_upcoming_vacation_working_days(conn, 1)
        assert result == 0
        conn.close()


# --- calculate_user_weight with vacation bonus ---


class TestCalculateUserWeightVacationBonus:
    def _weight(self, **kwargs):
        """Helper to call calculate_user_weight with sensible defaults."""
        defaults = {
            "user_id": 1,
            "last_selected": None,
            "last_working_day_catcher_id": None,
            "recent_selections": 0,
            "total_selections": 0,
            "avg_total_selections": 0,
            "has_alternatives": True,
            "upcoming_vacation_days": 0,
        }
        defaults.update(kwargs)
        return calculate_user_weight(**defaults)

    def test_zero_vacation_days_no_bonus(self):
        w_no_vac = self._weight(upcoming_vacation_days=0)
        w_default = self._weight()
        assert w_no_vac == w_default

    def test_vacation_days_increase_weight(self):
        w_no_vac = self._weight(
            last_selected="2025-01-01",
            recent_selections=2,
            total_selections=5,
            avg_total_selections=5,
            upcoming_vacation_days=0,
        )
        w_with_vac = self._weight(
            last_selected="2025-01-01",
            recent_selections=2,
            total_selections=5,
            avg_total_selections=5,
            upcoming_vacation_days=3,
        )
        assert w_with_vac > w_no_vac
        assert w_with_vac - w_no_vac == pytest.approx(
            3 * VACATION_LOOKAHEAD_BONUS, abs=0.01
        )

    def test_five_day_vacation_bonus(self):
        w_base = self._weight(
            last_selected="2025-01-01",
            upcoming_vacation_days=0,
        )
        w_five = self._weight(
            last_selected="2025-01-01",
            upcoming_vacation_days=5,
        )
        expected_bonus = 5 * VACATION_LOOKAHEAD_BONUS
        assert w_five - w_base == pytest.approx(expected_bonus, abs=0.01)

    def test_vacation_bonus_applied_before_consecutive_penalty(self):
        """Vacation bonus should be crushed by the consecutive-day penalty."""
        w_consec_no_vac = self._weight(
            last_selected="2025-01-01",
            last_working_day_catcher_id=1,
            upcoming_vacation_days=0,
        )
        w_consec_with_vac = self._weight(
            last_selected="2025-01-01",
            last_working_day_catcher_id=1,
            upcoming_vacation_days=3,
        )
        # The vacation bonus is added before the 0.1× penalty,
        # so the difference should be bonus * 0.1
        bonus = 3 * VACATION_LOOKAHEAD_BONUS
        assert w_consec_with_vac - w_consec_no_vac == pytest.approx(
            bonus * 0.1, abs=0.5
        )

    def test_backward_compatible_without_parameter(self):
        """Calling without upcoming_vacation_days should work (default=0)."""
        w = calculate_user_weight(1, None, None, 0, 0, 0, True)
        assert w >= 500  # Never-selected bonus still applies


# --- debug_weights output with vacation bonus ---


class TestDebugWeightsVacationBonus:
    @freeze_time("2026-09-08")  # Tuesday — users with weekdays 1,2,3,4,5 are available
    def test_debug_output_includes_vacation_days(self, db):
        """The debug_weights output should include upcoming vacation info."""
        db.execute("UPDATE user SET weekdays = ?", ("0,1,2,3,4,5,6",))

        # Give alice vacation Wed-Fri this week
        db.execute(
            "INSERT INTO vacation (user_id, start_date, end_date) "
            "VALUES (1, '2026-09-09', '2026-09-11')",
        )
        db.commit()

        log_messages: list[str] = []
        handler = logging.Handler()
        handler.emit = lambda record: log_messages.append(record.getMessage())
        handler.setLevel(logging.DEBUG)

        logger = logging.getLogger()
        original_level = logger.level
        logger.setLevel(logging.DEBUG)
        logger.addHandler(handler)

        try:
            with (
                patch("catcher.is_user_on_vacation", return_value=False),
                patch("catcher.get_last_working_day_catcher", return_value=None),
            ):
                find_next_catcher(
                    conn=db, tenant_id=1, dry_run=True, debug_weights=True
                )
        finally:
            logger.removeHandler(handler)
            logger.setLevel(original_level)

        # Check that at least one log message contains vacation lookahead info
        all_output = "\n".join(log_messages)
        assert "upcoming_vacation_days=" in all_output
