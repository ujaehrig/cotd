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
from pathlib import Path


@pytest.fixture
def test_db_with_tenants(tmp_path):
    """Create a test database with tenants and users."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)

    # Create tenants table
    schema_path = Path(__file__).parent.parent / "schema_tenants.sql"
    conn.executescript(schema_path.read_text())

    # Add test tenants
    conn.execute(
        "INSERT INTO tenants (name, location, webhook_url, active, slack_channel_id) VALUES (?, ?, ?, ?, ?)",
        ("Team Alpha", "BW", "https://example.com/alpha", 1, "C12345"),
    )
    conn.execute(
        "INSERT INTO tenants (name, location, webhook_url, active, slack_channel_id) VALUES (?, ?, ?, ?, ?)",
        ("Team Beta", "BY", "https://example.com/beta", 1, "C67890"),
    )
    conn.execute(
        "INSERT INTO tenants (name, location, webhook_url, active, slack_channel_id) VALUES (?, ?, ?, ?, ?)",
        ("Team Inactive", "BE", "https://example.com/inactive", 0, "C99999"),
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

    # Add users to tenants
    conn.execute(
        "INSERT INTO user (mail, weekdays, tenant_id) VALUES (?, ?, ?)",
        ("alpha1@example.com", "1,2,3,4,5", 1),
    )
    conn.execute(
        "INSERT INTO user (mail, weekdays, tenant_id) VALUES (?, ?, ?)",
        ("alpha2@example.com", "1,2,3,4,5", 1),
    )
    conn.execute(
        "INSERT INTO user (mail, weekdays, tenant_id) VALUES (?, ?, ?)",
        ("beta1@example.com", "1,2,3,4,5", 2),
    )
    conn.execute(
        "INSERT INTO user (mail, weekdays, tenant_id) VALUES (?, ?, ?)",
        ("beta2@example.com", "1,2,3,4,5", 2),
    )
    conn.commit()
    conn.close()

    return db_path


def test_get_tenant_by_name(test_db_with_tenants):
    """Test retrieving tenant by name."""
    from catcher import get_tenant_by_name

    conn = sqlite3.connect(test_db_with_tenants)
    tenant = get_tenant_by_name(conn, "Team Alpha")
    conn.close()

    assert tenant is not None
    assert tenant["name"] == "Team Alpha"
    assert tenant["location"] == "BW"
    assert tenant["webhook_url"] == "https://example.com/alpha"


def test_get_tenant_by_name_not_found(test_db_with_tenants):
    """Test retrieving non-existent tenant returns None."""
    from catcher import get_tenant_by_name

    conn = sqlite3.connect(test_db_with_tenants)
    tenant = get_tenant_by_name(conn, "NonExistent")
    conn.close()

    assert tenant is None


def test_get_active_tenants(test_db_with_tenants):
    """Test retrieving all active tenants."""
    from catcher import get_active_tenants

    conn = sqlite3.connect(test_db_with_tenants)
    tenants = get_active_tenants(conn)
    conn.close()

    assert len(tenants) == 2
    assert tenants[0]["name"] == "Team Alpha"
    assert tenants[1]["name"] == "Team Beta"


def test_get_active_tenants_excludes_inactive(test_db_with_tenants):
    """Test that inactive tenants are excluded."""
    from catcher import get_active_tenants

    conn = sqlite3.connect(test_db_with_tenants)
    tenants = get_active_tenants(conn)
    conn.close()

    tenant_names = [t["name"] for t in tenants]
    assert "Team Inactive" not in tenant_names


def test_process_tenant_returns_success(test_db_with_tenants):
    """Test processing a single tenant returns success."""
    from catcher import process_tenant, get_tenant_by_name
    from unittest.mock import patch

    conn = sqlite3.connect(test_db_with_tenants)
    tenant = get_tenant_by_name(conn, "Team Alpha")

    # Mock external dependencies
    with (
        patch("catcher.is_weekend", return_value=False),
        patch("catcher.is_holiday", return_value=False),
        patch(
            "catcher.find_next_catcher",
            return_value=("alpha1@example.com", True),
        ),
        patch("catcher.trigger_slack", return_value=True),
    ):
        from catcher import process_tenant

        success = process_tenant(
            conn, tenant, dry_run=True, debug_weights=False, force_notify=False
        )

    conn.close()
    assert success is True


def test_process_tenant_handles_weekend(test_db_with_tenants):
    """Test processing tenant on weekend returns success without selection."""
    from catcher import process_tenant, get_tenant_by_name
    from unittest.mock import patch

    conn = sqlite3.connect(test_db_with_tenants)
    tenant = get_tenant_by_name(conn, "Team Alpha")

    with patch("catcher.is_weekend", return_value=True):
        from catcher import process_tenant

        success = process_tenant(
            conn, tenant, dry_run=True, debug_weights=False, force_notify=False
        )

    conn.close()
    assert success is True


def test_process_tenant_handles_errors(test_db_with_tenants):
    """Test processing tenant handles errors gracefully."""
    from catcher import process_tenant, get_tenant_by_name
    from unittest.mock import patch

    conn = sqlite3.connect(test_db_with_tenants)
    tenant = get_tenant_by_name(conn, "Team Alpha")

    with patch("catcher.is_weekend", side_effect=Exception("Test error")):
        from catcher import process_tenant

        success = process_tenant(
            conn, tenant, dry_run=True, debug_weights=False, force_notify=False
        )

    conn.close()
    assert success is False
