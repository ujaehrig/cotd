"""Tests for catcher.py core functions."""

import sqlite3
import datetime
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from catcher import (
    cleanup_old_vacations,
    get_tenant_by_name,
    get_active_tenants,
    is_user_on_vacation,
    get_recent_selection_count,
    cleanup_old_selection_history,
    calculate_user_weight,
    add_tie_breaking_logic,
    weighted_random_selection_improved,
    trigger_slack,
    is_weekend,
    is_holiday,
    process_tenant,
    find_next_catcher,
)


@pytest.fixture
def db(tmp_path):
    """Create a fully-populated test database."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    schema_path = Path(__file__).parent / "schema_tenants.sql"
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
            FOREIGN KEY (user_id) REFERENCES user(id)
        );
        CREATE TABLE IF NOT EXISTS selection_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            selected_date DATE NOT NULL,
            FOREIGN KEY (user_id) REFERENCES user(id)
        );
    """)

    # Seed tenants
    conn.execute(
        "INSERT INTO tenants (name, location, webhook_url, active) VALUES (?, ?, ?, ?)",
        ("Team Alpha", "BW", "https://hooks.example.com/alpha", 1),
    )
    conn.execute(
        "INSERT INTO tenants (name, location, webhook_url, active) VALUES (?, ?, ?, ?)",
        ("Team Inactive", "BY", "https://hooks.example.com/inactive", 0),
    )

    # Seed users for Team Alpha (tenant_id=1)
    conn.execute(
        "INSERT INTO user (mail, weekdays, last_chosen, tenant_id) VALUES (?, ?, ?, ?)",
        ("alice@example.com", "0,1,2,3,4", "2026-03-01", 1),
    )
    conn.execute(
        "INSERT INTO user (mail, weekdays, last_chosen, tenant_id) VALUES (?, ?, ?, ?)",
        ("bob@example.com", "0,1,2,3,4", "2026-03-20", 1),
    )
    conn.commit()
    yield conn
    conn.close()


# --- cleanup_old_vacations ---


class TestCleanupOldVacations:
    def test_deletes_old_entries(self, db):
        old_date = (datetime.datetime.now() - datetime.timedelta(days=200)).date().isoformat()
        db.execute(
            "INSERT INTO vacation (user_id, start_date, end_date) VALUES (1, ?, ?)",
            (old_date, old_date),
        )
        db.commit()
        cleanup_old_vacations(db)
        count = db.execute("SELECT COUNT(*) FROM vacation").fetchone()[0]
        assert count == 0

    def test_keeps_recent_entries(self, db):
        recent = (datetime.datetime.now() - datetime.timedelta(days=10)).date().isoformat()
        db.execute(
            "INSERT INTO vacation (user_id, start_date, end_date) VALUES (1, ?, ?)",
            (recent, recent),
        )
        db.commit()
        cleanup_old_vacations(db)
        count = db.execute("SELECT COUNT(*) FROM vacation").fetchone()[0]
        assert count == 1

    def test_dry_run_does_not_delete(self, db):
        old_date = (datetime.datetime.now() - datetime.timedelta(days=200)).date().isoformat()
        db.execute(
            "INSERT INTO vacation (user_id, start_date, end_date) VALUES (1, ?, ?)",
            (old_date, old_date),
        )
        db.commit()
        cleanup_old_vacations(db, dry_run=True)
        count = db.execute("SELECT COUNT(*) FROM vacation").fetchone()[0]
        assert count == 1


# --- tenant functions ---


class TestGetTenantByName:
    def test_found(self, db):
        t = get_tenant_by_name(db, "Team Alpha")
        assert t is not None
        assert t["name"] == "Team Alpha"
        assert t["location"] == "BW"
        assert t["ical_url"] is None

    def test_not_found(self, db):
        assert get_tenant_by_name(db, "Nope") is None


class TestGetActiveTenants:
    def test_excludes_inactive(self, db):
        tenants = get_active_tenants(db)
        names = [t["name"] for t in tenants]
        assert "Team Alpha" in names
        assert "Team Inactive" not in names


# --- is_user_on_vacation ---


class TestIsUserOnVacation:
    def test_on_vacation(self, db):
        db.execute(
            "INSERT INTO vacation (user_id, start_date, end_date) VALUES (1, '2026-04-01', '2026-04-10')"
        )
        db.commit()
        assert is_user_on_vacation(db, 1, "2026-04-05") is True

    def test_not_on_vacation(self, db):
        assert is_user_on_vacation(db, 1, "2026-04-05") is False

    def test_boundary_start(self, db):
        db.execute(
            "INSERT INTO vacation (user_id, start_date, end_date) VALUES (1, '2026-04-05', '2026-04-10')"
        )
        db.commit()
        assert is_user_on_vacation(db, 1, "2026-04-05") is True

    def test_boundary_end(self, db):
        db.execute(
            "INSERT INTO vacation (user_id, start_date, end_date) VALUES (1, '2026-04-01', '2026-04-05')"
        )
        db.commit()
        assert is_user_on_vacation(db, 1, "2026-04-05") is True


# --- get_recent_selection_count ---


class TestGetRecentSelectionCount:
    def test_counts_recent(self, db):
        today = datetime.date.today().isoformat()
        db.execute(
            "INSERT INTO selection_history (user_id, selected_date) VALUES (1, ?)",
            (today,),
        )
        db.commit()
        assert get_recent_selection_count(db, 1) >= 1

    def test_zero_when_none(self, db):
        assert get_recent_selection_count(db, 1) == 0


# --- cleanup_old_selection_history ---


class TestCleanupOldSelectionHistory:
    def test_deletes_old_records(self, db):
        old = (datetime.date.today() - datetime.timedelta(days=400)).isoformat()
        db.execute(
            "INSERT INTO selection_history (user_id, selected_date) VALUES (1, ?)",
            (old,),
        )
        db.commit()
        cleanup_old_selection_history(db)
        count = db.execute("SELECT COUNT(*) FROM selection_history").fetchone()[0]
        assert count == 0

    def test_keeps_recent_records(self, db):
        recent = datetime.date.today().isoformat()
        db.execute(
            "INSERT INTO selection_history (user_id, selected_date) VALUES (1, ?)",
            (recent,),
        )
        db.commit()
        cleanup_old_selection_history(db)
        count = db.execute("SELECT COUNT(*) FROM selection_history").fetchone()[0]
        assert count == 1


# --- calculate_user_weight ---


class TestCalculateUserWeight:
    def test_never_selected_gets_high_bonus(self):
        w = calculate_user_weight(1, None, None, 0, 0, 0, True)
        assert w >= 500

    def test_recently_selected_lower_weight(self):
        today = datetime.date.today().isoformat()
        w = calculate_user_weight(1, today, None, 5, 10, 10, True)
        w_old = calculate_user_weight(2, "2025-01-01", None, 0, 0, 10, True)
        assert w < w_old

    def test_consecutive_day_penalty(self):
        w_normal = calculate_user_weight(1, "2026-03-01", None, 0, 0, 0, True)
        w_consecutive = calculate_user_weight(1, "2026-03-01", 1, 0, 0, 0, True)
        assert w_consecutive < w_normal

    def test_no_consecutive_penalty_without_alternatives(self):
        w = calculate_user_weight(1, "2026-03-01", 1, 0, 0, 0, False)
        w_normal = calculate_user_weight(1, "2026-03-01", None, 0, 0, 0, False)
        assert w == w_normal

    def test_weight_always_positive(self):
        w = calculate_user_weight(1, datetime.date.today().isoformat(), 1, 100, 100, 1, True)
        assert w >= 1


# --- add_tie_breaking_logic ---


class TestAddTieBreakingLogic:
    def test_single_user_unchanged(self):
        users = [{"user": {"mail": "a@b.com", "last_chosen": None}, "weight": 100}]
        result = add_tie_breaking_logic(users)
        assert len(result) == 1
        assert result[0]["weight"] == 100

    def test_tied_users_get_different_weights(self):
        users = [
            {"user": {"mail": "a@b.com", "last_chosen": "2026-01-01"}, "weight": 100},
            {"user": {"mail": "b@b.com", "last_chosen": "2026-02-01"}, "weight": 100},
        ]
        result = add_tie_breaking_logic(users)
        weights = [u["weight"] for u in result]
        assert len(set(weights)) == 2  # Different weights

    def test_never_selected_wins_tie(self):
        users = [
            {"user": {"mail": "recent@b.com", "last_chosen": "2026-03-01"}, "weight": 100},
            {"user": {"mail": "never@b.com", "last_chosen": None}, "weight": 100},
        ]
        result = add_tie_breaking_logic(users)
        # Never-selected should get higher tie-breaker
        never = next(u for u in result if u["user"]["mail"] == "never@b.com")
        recent = next(u for u in result if u["user"]["mail"] == "recent@b.com")
        assert never["weight"] > recent["weight"]


# --- weighted_random_selection_improved ---


class TestWeightedRandomSelection:
    def test_single_user(self):
        users = [{"user": {"mail": "a@b.com"}, "weight": 100}]
        assert weighted_random_selection_improved(users)["mail"] == "a@b.com"

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            weighted_random_selection_improved([])

    def test_heavily_weighted_user_selected(self):
        users = [
            {"user": {"mail": "heavy@b.com"}, "weight": 10000},
            {"user": {"mail": "light@b.com"}, "weight": 1},
        ]
        # Run many times — heavy should win almost always
        results = [weighted_random_selection_improved(users)["mail"] for _ in range(100)]
        assert results.count("heavy@b.com") > 80


# --- trigger_slack ---


class TestTriggerSlack:
    def test_dry_run_returns_true(self):
        assert trigger_slack("a@b.com", "https://hook", dry_run=True) is True

    def test_empty_mail_returns_false(self):
        assert trigger_slack("", "https://hook") is False

    def test_no_webhook_returns_false(self):
        assert trigger_slack("a@b.com", "") is False

    @patch("catcher.requests.post")
    def test_success(self, mock_post):
        mock_post.return_value = MagicMock(status_code=200)
        assert trigger_slack("a@b.com", "https://hook") is True

    @patch("catcher.requests.post")
    def test_client_error_no_retry(self, mock_post):
        mock_post.return_value = MagicMock(status_code=400, text="Bad Request")
        assert trigger_slack("a@b.com", "https://hook") is False
        assert mock_post.call_count == 1

    @patch("catcher.requests.post")
    @patch("catcher.time.sleep")
    def test_server_error_retries(self, mock_sleep, mock_post):
        mock_post.return_value = MagicMock(status_code=500)
        assert trigger_slack("a@b.com", "https://hook", max_retries=2) is False
        assert mock_post.call_count == 2

    @patch("catcher.requests.post")
    def test_request_exception(self, mock_post):
        import requests as req
        mock_post.side_effect = req.exceptions.ConnectionError("fail")
        assert trigger_slack("a@b.com", "https://hook") is False


# --- is_weekend ---


class TestIsWeekend:
    @patch("catcher.datetime")
    def test_saturday(self, mock_dt):
        mock_dt.datetime.now.return_value.weekday.return_value = 5
        mock_dt.date = datetime.date
        mock_dt.timedelta = datetime.timedelta
        assert is_weekend() is True

    @patch("catcher.datetime")
    def test_monday(self, mock_dt):
        mock_dt.datetime.now.return_value.weekday.return_value = 0
        mock_dt.date = datetime.date
        mock_dt.timedelta = datetime.timedelta
        assert is_weekend() is False


# --- is_holiday ---


class TestIsHoliday:
    @patch("catcher.requests.get")
    def test_api_returns_200_is_holiday(self, mock_get):
        mock_get.return_value = MagicMock(status_code=200)
        assert is_holiday("BW") is True

    @patch("catcher.requests.get")
    def test_api_returns_204_not_holiday(self, mock_get):
        mock_get.return_value = MagicMock(status_code=204)
        assert is_holiday("BW") is False

    @patch("catcher.holidays.Germany")
    @patch("catcher.requests.get")
    def test_api_failure_falls_back_to_library(self, mock_get, mock_holidays):
        import requests as req
        mock_get.side_effect = req.exceptions.ConnectionError("fail")
        mock_holidays_instance = MagicMock()
        mock_holidays_instance.__contains__ = MagicMock(return_value=False)
        mock_holidays.return_value = mock_holidays_instance
        assert is_holiday("BW") is False


# --- process_tenant ---


class TestProcessTenant:
    def _tenant_dict(self):
        return {
            "id": 1,
            "name": "Team Alpha",
            "location": "BW",
            "webhook_url": "https://hooks.example.com/alpha",
            "active": 1,
            "ical_url": None,
        }

    @patch("catcher.trigger_slack", return_value=True)
    @patch("catcher.find_next_catcher", return_value=("alice@example.com", True))
    @patch("catcher.is_holiday", return_value=False)
    @patch("catcher.is_weekend", return_value=False)
    def test_success(self, *mocks):
        db = MagicMock()
        assert process_tenant(db, self._tenant_dict(), dry_run=True) is True

    @patch("catcher.is_weekend", return_value=True)
    def test_weekend_returns_true(self, _):
        db = MagicMock()
        assert process_tenant(db, self._tenant_dict()) is True

    @patch("catcher.is_holiday", return_value=True)
    @patch("catcher.is_weekend", return_value=False)
    def test_holiday_returns_true(self, *_):
        db = MagicMock()
        assert process_tenant(db, self._tenant_dict()) is True

    @patch("catcher.is_weekend", side_effect=Exception("boom"))
    def test_exception_returns_false(self, _):
        db = MagicMock()
        assert process_tenant(db, self._tenant_dict()) is False


# --- find_next_catcher ---


class TestFindNextCatcherWeighted:
    def test_selects_user_dry_run(self, db):
        # Ensure users are available on today's weekday
        db.execute("UPDATE user SET weekdays = ?", ("0,1,2,3,4,5,6",))
        db.commit()

        with (
            patch("catcher.is_user_on_vacation", return_value=False),
            patch("catcher.get_last_working_day_catcher", return_value=None),
        ):
            mail, is_new = find_next_catcher(conn=db, tenant_id=1, dry_run=True)
            assert mail in ("alice@example.com", "bob@example.com")
            assert is_new is True

    def test_returns_existing_selection(self, db):
        today = datetime.date.today().isoformat()
        db.execute("UPDATE user SET weekdays = ?", ("0,1,2,3,4,5,6",))
        db.execute(
            "INSERT INTO selection_history (user_id, selected_date) VALUES (1, ?)",
            (today,),
        )
        db.commit()

        mail, is_new = find_next_catcher(conn=db, tenant_id=1)
        assert mail == "alice@example.com"
        assert is_new is False

    def test_no_available_users(self, db):
        # Set weekdays to something that doesn't match today
        impossible_day = str((datetime.datetime.now().weekday() + 3) % 7)
        db.execute("UPDATE user SET weekdays = ?", (impossible_day,))
        db.commit()

        mail, is_new = find_next_catcher(conn=db, tenant_id=1)
        assert mail is None
        assert is_new is False
