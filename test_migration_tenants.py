#!/usr/bin/env -S uv run --script

# /// script
# dependencies = [
#    "pytest>=7.0.0",
#    "python-dotenv>=1.0.0",
# ]
# ///

import sqlite3
import pytest
import os
from unittest.mock import patch


@pytest.fixture
def temp_db(tmp_path):
    """Create a temporary database for testing."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    yield conn, db_path
    conn.close()


@pytest.fixture
def existing_user_db(tmp_path):
    """Create a database with existing user table (pre-migration state)."""
    db_path = tmp_path / "existing.db"
    conn = sqlite3.connect(db_path)

    # Create old user table structure
    conn.execute("""
        CREATE TABLE user (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            weekdays VARCHAR(10),
            mail VARCHAR(50) UNIQUE NOT NULL,
            last_chosen DATE
        )
    """)

    # Add some test users
    conn.execute(
        "INSERT INTO user (mail, weekdays) VALUES (?, ?)",
        ("user1@example.com", "0,1,2,3,4"),
    )
    conn.execute(
        "INSERT INTO user (mail, weekdays) VALUES (?, ?)",
        ("user2@example.com", "0,1,2,3,4"),
    )
    conn.execute(
        "INSERT INTO user (mail, weekdays) VALUES (?, ?)",
        ("user3@example.com", "1,2,3"),
    )
    conn.commit()

    yield conn, db_path
    conn.close()


def test_migration_creates_tenants_table(temp_db):
    """Test that migration creates tenants table."""
    conn, db_path = temp_db

    # Import and run migration
    from migrate_to_tenants import migrate_database

    with patch.dict(
        os.environ,
        {"SLACK_WEBHOOK_URL": "https://example.com/webhook", "HOLIDAY_REGION": "BW"},
    ):
        migrate_database(str(db_path))

    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='tenants'"
    )
    assert cursor.fetchone() is not None


def test_migration_creates_default_tenant(existing_user_db):
    """Test that migration creates default tenant 'Team Challengers'."""
    conn, db_path = existing_user_db

    from migrate_to_tenants import migrate_database

    with patch.dict(
        os.environ,
        {"SLACK_WEBHOOK_URL": "https://example.com/webhook", "HOLIDAY_REGION": "BW"},
    ):
        migrate_database(str(db_path))

    cursor = conn.execute(
        "SELECT name, location, webhook_url FROM tenants WHERE name = ?",
        ("Team Challengers",),
    )
    tenant = cursor.fetchone()
    assert tenant is not None
    assert tenant[0] == "Team Challengers"
    assert tenant[1] == "BW"
    assert tenant[2] == "https://example.com/webhook"


def test_migration_adds_tenant_id_column(existing_user_db):
    """Test that migration adds tenant_id column to user table."""
    conn, db_path = existing_user_db

    from migrate_to_tenants import migrate_database

    with patch.dict(
        os.environ,
        {"SLACK_WEBHOOK_URL": "https://example.com/webhook", "HOLIDAY_REGION": "BW"},
    ):
        migrate_database(str(db_path))

    cursor = conn.execute("PRAGMA table_info(user)")
    columns = {row[1] for row in cursor.fetchall()}
    assert "tenant_id" in columns


def test_migration_assigns_users_to_default_tenant(existing_user_db):
    """Test that all existing users are assigned to default tenant."""
    conn, db_path = existing_user_db

    from migrate_to_tenants import migrate_database

    with patch.dict(
        os.environ,
        {"SLACK_WEBHOOK_URL": "https://example.com/webhook", "HOLIDAY_REGION": "BW"},
    ):
        migrate_database(str(db_path))

    # Get default tenant id
    cursor = conn.execute(
        "SELECT id FROM tenants WHERE name = ?", ("Team Challengers",)
    )
    tenant_id = cursor.fetchone()[0]

    # Check all users have this tenant_id
    cursor = conn.execute("SELECT COUNT(*) FROM user WHERE tenant_id = ?", (tenant_id,))
    user_count = cursor.fetchone()[0]
    assert user_count == 3


def test_migration_preserves_user_data(existing_user_db):
    """Test that migration preserves all existing user data."""
    conn, db_path = existing_user_db

    # Get original data
    cursor = conn.execute("SELECT mail, weekdays FROM user ORDER BY mail")
    original_users = cursor.fetchall()

    from migrate_to_tenants import migrate_database

    with patch.dict(
        os.environ,
        {"SLACK_WEBHOOK_URL": "https://example.com/webhook", "HOLIDAY_REGION": "BW"},
    ):
        migrate_database(str(db_path))

    # Check data preserved
    cursor = conn.execute("SELECT mail, weekdays FROM user ORDER BY mail")
    migrated_users = cursor.fetchall()
    assert migrated_users == original_users


def test_migration_is_idempotent(existing_user_db):
    """Test that running migration twice doesn't cause errors."""
    conn, db_path = existing_user_db

    from migrate_to_tenants import migrate_database

    with patch.dict(
        os.environ,
        {"SLACK_WEBHOOK_URL": "https://example.com/webhook", "HOLIDAY_REGION": "BW"},
    ):
        # Run migration twice
        migrate_database(str(db_path))
        migrate_database(str(db_path))

    # Check only one default tenant exists
    cursor = conn.execute(
        "SELECT COUNT(*) FROM tenants WHERE name = ?", ("Team Challengers",)
    )
    count = cursor.fetchone()[0]
    assert count == 1

    # Check users still assigned correctly
    cursor = conn.execute("SELECT COUNT(*) FROM user WHERE tenant_id IS NOT NULL")
    user_count = cursor.fetchone()[0]
    assert user_count == 3


def test_migration_handles_empty_database(temp_db):
    """Test that migration works on empty database."""
    conn, db_path = temp_db

    from migrate_to_tenants import migrate_database

    with patch.dict(
        os.environ,
        {"SLACK_WEBHOOK_URL": "https://example.com/webhook", "HOLIDAY_REGION": "BW"},
    ):
        migrate_database(str(db_path))

    # Check tenants table exists
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='tenants'"
    )
    assert cursor.fetchone() is not None

    # Check default tenant created
    cursor = conn.execute(
        "SELECT COUNT(*) FROM tenants WHERE name = ?", ("Team Challengers",)
    )
    assert cursor.fetchone()[0] == 1


def test_migration_uses_env_defaults(existing_user_db):
    """Test that migration uses environment variable defaults."""
    conn, db_path = existing_user_db

    from migrate_to_tenants import migrate_database

    with patch.dict(
        os.environ,
        {
            "SLACK_WEBHOOK_URL": "https://custom.webhook.url/test",
            "HOLIDAY_REGION": "BY",
        },
    ):
        migrate_database(str(db_path))

    cursor = conn.execute(
        "SELECT location, webhook_url FROM tenants WHERE name = ?",
        ("Team Challengers",),
    )
    tenant = cursor.fetchone()
    assert tenant[0] == "BY"
    assert tenant[1] == "https://custom.webhook.url/test"


def test_migration_handles_missing_env_vars(existing_user_db):
    """Test that migration uses sensible defaults when env vars missing."""
    conn, db_path = existing_user_db

    from migrate_to_tenants import migrate_database

    with patch.dict(os.environ, {}, clear=True):
        migrate_database(str(db_path))

    cursor = conn.execute(
        "SELECT location, webhook_url FROM tenants WHERE name = ?",
        ("Team Challengers",),
    )
    tenant = cursor.fetchone()
    assert tenant[0] == "BW"  # Default location
    assert tenant[1] != ""  # Should have some default webhook
