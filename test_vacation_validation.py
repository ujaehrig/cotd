"""Tests for vacation validation functions in manage_vacations.py."""

import sqlite3
import pytest
from unittest.mock import patch

from manage_vacations import check_vacation_overlap, check_duplicate_vacation


@pytest.fixture
def db_with_vacation(tmp_path):
    """Create a test DB with a user and one vacation."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE user (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mail VARCHAR(50) UNIQUE NOT NULL,
            weekdays VARCHAR(10),
            last_chosen DATE
        )
    """)
    conn.execute("""
        CREATE TABLE vacation (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            start_date DATE NOT NULL,
            end_date DATE NOT NULL,
            FOREIGN KEY (user_id) REFERENCES user(id)
        )
    """)
    conn.execute(
        "INSERT INTO user (mail, weekdays) VALUES ('test@example.com', '1,2,3,4,5')"
    )
    conn.execute(
        "INSERT INTO vacation (user_id, start_date, end_date) VALUES (1, '2025-12-10', '2025-12-15')"
    )
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture(autouse=True)
def mock_db(db_with_vacation):
    """Patch get_db_connection to use the temp DB."""
    def _get_conn():
        conn = sqlite3.connect(db_with_vacation)
        conn.row_factory = sqlite3.Row
        return conn

    with patch("manage_vacations.get_db_connection", _get_conn):
        yield


class TestCheckDuplicateVacation:
    def test_exact_duplicate(self):
        is_dup, msg = check_duplicate_vacation(1, "2025-12-10", "2025-12-15")
        assert is_dup is True
        assert "already have" in msg

    def test_not_duplicate(self):
        is_dup, _ = check_duplicate_vacation(1, "2025-12-20", "2025-12-25")
        assert is_dup is False

    def test_single_day_duplicate_message(self, db_with_vacation):
        conn = sqlite3.connect(db_with_vacation)
        conn.execute(
            "INSERT INTO vacation (user_id, start_date, end_date) VALUES (1, '2025-12-25', '2025-12-25')"
        )
        conn.commit()
        conn.close()
        is_dup, msg = check_duplicate_vacation(1, "2025-12-25", "2025-12-25")
        assert is_dup is True
        assert "on 2025-12-25" in msg


class TestCheckVacationOverlap:
    def test_overlap_starts_before_ends_during(self):
        has, msg = check_vacation_overlap(1, "2025-12-08", "2025-12-12")
        assert has is True
        assert "overlaps" in msg

    def test_overlap_starts_during_ends_after(self):
        has, _ = check_vacation_overlap(1, "2025-12-12", "2025-12-18")
        assert has is True

    def test_overlap_completely_contains(self):
        has, _ = check_vacation_overlap(1, "2025-12-08", "2025-12-18")
        assert has is True

    def test_overlap_contained_within(self):
        has, _ = check_vacation_overlap(1, "2025-12-12", "2025-12-14")
        assert has is True

    def test_no_overlap_before(self):
        has, _ = check_vacation_overlap(1, "2025-12-05", "2025-12-08")
        assert has is False

    def test_no_overlap_after(self):
        has, _ = check_vacation_overlap(1, "2025-12-17", "2025-12-20")
        assert has is False
