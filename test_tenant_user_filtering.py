#!/usr/bin/env -S uv run --script

# /// script
# dependencies = [
#    "pytest>=7.0.0",
#    "requests>=2.25.0",
#    "python-dotenv>=1.0.0",
#    "holidays>=0.34"
# ]
# ///

import sqlite3
import pytest
import datetime
from pathlib import Path


@pytest.fixture
def test_db_with_tenant_users(tmp_path):
    """Create a test database with tenants and users."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)

    # Create tenants table
    schema_path = Path(__file__).parent / "schema_tenants.sql"
    conn.executescript(schema_path.read_text())

    # Add test tenants
    conn.execute(
        "INSERT INTO tenants (name, location, webhook_url, active) VALUES (?, ?, ?, ?)",
        ("Team Alpha", "BW", "https://example.com/alpha", 1),
    )
    conn.execute(
        "INSERT INTO tenants (name, location, webhook_url, active) VALUES (?, ?, ?, ?)",
        ("Team Beta", "BY", "https://example.com/beta", 1),
    )
    conn.commit()

    # Create user table with tenant_id
    conn.execute("""
        CREATE TABLE user (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mail VARCHAR(50) UNIQUE NOT NULL,
            weekdays VARCHAR(10),
            last_chosen DATE,
            tenant_id INTEGER REFERENCES tenants(id)
        )
    """)

    # Create vacation table
    conn.execute("""
        CREATE TABLE vacation (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER REFERENCES user(id),
            start_date DATE,
            end_date DATE
        )
    """)

    # Create selection_history table
    conn.execute("""
        CREATE TABLE selection_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER REFERENCES user(id),
            selected_date DATE
        )
    """)

    # Add users to tenants (available all days so tests don't depend on current weekday)
    conn.execute(
        "INSERT INTO user (mail, weekdays, tenant_id) VALUES (?, ?, ?)",
        ("alpha1@example.com", "0,1,2,3,4,5,6", 1),
    )
    conn.execute(
        "INSERT INTO user (mail, weekdays, tenant_id) VALUES (?, ?, ?)",
        ("alpha2@example.com", "0,1,2,3,4,5,6", 1),
    )
    conn.execute(
        "INSERT INTO user (mail, weekdays, tenant_id) VALUES (?, ?, ?)",
        ("beta1@example.com", "0,1,2,3,4,5,6", 2),
    )
    conn.execute(
        "INSERT INTO user (mail, weekdays, tenant_id) VALUES (?, ?, ?)",
        ("beta2@example.com", "0,1,2,3,4,5,6", 2),
    )
    conn.commit()
    conn.close()

    return db_path


def test_find_next_catcher_filters_by_tenant(test_db_with_tenant_users):
    """Test that find_next_catcher filters users by tenant_id."""
    from catcher import find_next_catcher
    from unittest.mock import patch

    conn = sqlite3.connect(test_db_with_tenant_users)

    # Mock weekend and holiday checks
    with (
        patch("catcher.is_weekend", return_value=False),
        patch("catcher.is_holiday", return_value=False),
    ):
        # Should only return users from tenant 1
        mail, is_new = find_next_catcher(conn, tenant_id=1, dry_run=True)

        assert mail is not None
        assert mail in ["alpha1@example.com", "alpha2@example.com"]
        assert mail not in ["beta1@example.com", "beta2@example.com"]

    conn.close()


def test_find_next_catcher_excludes_other_tenants(test_db_with_tenant_users):
    """Test that users from other tenants are not included."""
    from catcher import find_next_catcher
    from unittest.mock import patch

    conn = sqlite3.connect(test_db_with_tenant_users)

    with (
        patch("catcher.is_weekend", return_value=False),
        patch("catcher.is_holiday", return_value=False),
    ):
        # Process tenant 2
        mail, is_new = find_next_catcher(conn, tenant_id=2, dry_run=True)

        assert mail is not None
        assert mail in ["beta1@example.com", "beta2@example.com"]
        assert mail not in ["alpha1@example.com", "alpha2@example.com"]

    conn.close()


def test_find_next_catcher_returns_none_when_no_users(test_db_with_tenant_users):
    """Test that None is returned when tenant has no users."""
    from catcher import find_next_catcher
    from unittest.mock import patch

    conn = sqlite3.connect(test_db_with_tenant_users)

    # Add tenant with no users
    conn.execute(
        "INSERT INTO tenants (name, location, webhook_url, active) VALUES (?, ?, ?, ?)",
        ("Team Empty", "HH", "https://example.com/empty", 1),
    )
    conn.commit()

    with (
        patch("catcher.is_weekend", return_value=False),
        patch("catcher.is_holiday", return_value=False),
    ):
        mail, is_new = find_next_catcher(conn, tenant_id=3, dry_run=True)

        assert mail is None

    conn.close()


def test_vacation_filtering_per_tenant(test_db_with_tenant_users):
    """Test that vacation filtering works correctly per tenant."""
    from catcher import find_next_catcher
    from unittest.mock import patch

    conn = sqlite3.connect(test_db_with_tenant_users)

    # Put alpha1 on vacation
    today = datetime.date.today().isoformat()
    conn.execute(
        "INSERT INTO vacation (user_id, start_date, end_date) VALUES (?, ?, ?)",
        (1, today, today),
    )
    conn.commit()

    with (
        patch("catcher.is_weekend", return_value=False),
        patch("catcher.is_holiday", return_value=False),
    ):
        # Should only return alpha2 (alpha1 is on vacation)
        mail, is_new = find_next_catcher(conn, tenant_id=1, dry_run=True)

        assert mail == "alpha2@example.com"

    conn.close()


def test_weekday_filtering_per_tenant(test_db_with_tenant_users):
    """Test that weekday filtering works correctly per tenant."""
    from catcher import find_next_catcher
    from unittest.mock import patch

    conn = sqlite3.connect(test_db_with_tenant_users)

    # Set alpha1 to only work on a day that is NOT today
    today_weekday = datetime.datetime.now().strftime("%w")
    other_day = "1" if today_weekday != "1" else "2"
    conn.execute("UPDATE user SET weekdays = ? WHERE id = ?", (other_day, 1))
    conn.commit()

    with (
        patch("catcher.is_weekend", return_value=False),
        patch("catcher.is_holiday", return_value=False),
    ):
        # On a weekday, should only return alpha2
        mail, is_new = find_next_catcher(conn, tenant_id=1, dry_run=True)

        assert mail == "alpha2@example.com"

    conn.close()


def test_selection_history_scoped_per_tenant(test_db_with_tenant_users):
    """Test that selection history is properly scoped per tenant."""
    from catcher import find_next_catcher
    from unittest.mock import patch

    conn = sqlite3.connect(test_db_with_tenant_users)

    today = datetime.date.today().isoformat()

    # Add selection history for alpha1 today
    conn.execute(
        "INSERT INTO selection_history (user_id, selected_date) VALUES (?, ?)",
        (1, today),
    )
    conn.commit()

    with (
        patch("catcher.is_weekend", return_value=False),
        patch("catcher.is_holiday", return_value=False),
    ):
        # Should return alpha1 as already selected for tenant 1
        mail, is_new = find_next_catcher(conn, tenant_id=1, dry_run=True)

        assert mail == "alpha1@example.com"
        assert is_new is False  # Already selected today

        # Tenant 2 should still select someone new
        mail2, is_new2 = find_next_catcher(conn, tenant_id=2, dry_run=True)

        assert mail2 in ["beta1@example.com", "beta2@example.com"]
        assert is_new2 is True  # New selection for tenant 2

    conn.close()
