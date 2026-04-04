#!/usr/bin/env -S uv run --script

# /// script
# dependencies = [
#    "pytest>=7.0.0",
# ]
# ///

import sqlite3
import pytest
from pathlib import Path


@pytest.fixture
def temp_db(tmp_path):
    """Create a temporary database for testing."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    yield conn
    conn.close()


@pytest.fixture
def schema_sql():
    """Load the tenant schema SQL."""
    schema_path = Path(__file__).parent / "schema_tenants.sql"
    return schema_path.read_text()


def test_tenant_table_creation(temp_db, schema_sql):
    """Test that tenants table is created with correct structure."""
    temp_db.executescript(schema_sql)

    cursor = temp_db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='tenants'"
    )
    assert cursor.fetchone() is not None, "tenants table should exist"


def test_tenant_table_columns(temp_db, schema_sql):
    """Test that tenants table has all required columns."""
    temp_db.executescript(schema_sql)

    cursor = temp_db.execute("PRAGMA table_info(tenants)")
    columns = {row[1]: row[2] for row in cursor.fetchall()}

    assert "id" in columns
    assert "name" in columns
    assert "location" in columns
    assert "webhook_url" in columns
    assert "active" in columns
    assert "created_at" in columns


def test_tenant_name_unique_constraint(temp_db, schema_sql):
    """Test that tenant name must be unique."""
    temp_db.executescript(schema_sql)

    temp_db.execute(
        "INSERT INTO tenants (name, location, webhook_url) VALUES (?, ?, ?)",
        ("Test Team", "BW", "https://example.com/webhook"),
    )
    temp_db.commit()

    with pytest.raises(sqlite3.IntegrityError):
        temp_db.execute(
            "INSERT INTO tenants (name, location, webhook_url) VALUES (?, ?, ?)",
            ("Test Team", "BY", "https://example.com/webhook2"),
        )


def test_tenant_name_not_null(temp_db, schema_sql):
    """Test that tenant name cannot be null."""
    temp_db.executescript(schema_sql)

    with pytest.raises(sqlite3.IntegrityError):
        temp_db.execute(
            "INSERT INTO tenants (name, location, webhook_url) VALUES (?, ?, ?)",
            (None, "BW", "https://example.com/webhook"),
        )


def test_tenant_location_not_null(temp_db, schema_sql):
    """Test that tenant location cannot be null."""
    temp_db.executescript(schema_sql)

    with pytest.raises(sqlite3.IntegrityError):
        temp_db.execute(
            "INSERT INTO tenants (name, location, webhook_url) VALUES (?, ?, ?)",
            ("Test Team", None, "https://example.com/webhook"),
        )


def test_tenant_webhook_url_not_null(temp_db, schema_sql):
    """Test that tenant webhook_url cannot be null."""
    temp_db.executescript(schema_sql)

    with pytest.raises(sqlite3.IntegrityError):
        temp_db.execute(
            "INSERT INTO tenants (name, location, webhook_url) VALUES (?, ?, ?)",
            ("Test Team", "BW", None),
        )


def test_tenant_active_default_value(temp_db, schema_sql):
    """Test that active defaults to 1 (true)."""
    temp_db.executescript(schema_sql)

    temp_db.execute(
        "INSERT INTO tenants (name, location, webhook_url) VALUES (?, ?, ?)",
        ("Test Team", "BW", "https://example.com/webhook"),
    )
    temp_db.commit()

    cursor = temp_db.execute(
        "SELECT active FROM tenants WHERE name = ?", ("Test Team",)
    )
    active = cursor.fetchone()[0]
    assert active == 1


def test_tenant_created_at_default_value(temp_db, schema_sql):
    """Test that created_at has a default timestamp."""
    temp_db.executescript(schema_sql)

    temp_db.execute(
        "INSERT INTO tenants (name, location, webhook_url) VALUES (?, ?, ?)",
        ("Test Team", "BW", "https://example.com/webhook"),
    )
    temp_db.commit()

    cursor = temp_db.execute(
        "SELECT created_at FROM tenants WHERE name = ?", ("Test Team",)
    )
    created_at = cursor.fetchone()[0]
    assert created_at is not None


def test_tenant_id_autoincrement(temp_db, schema_sql):
    """Test that tenant id auto-increments."""
    temp_db.executescript(schema_sql)

    temp_db.execute(
        "INSERT INTO tenants (name, location, webhook_url) VALUES (?, ?, ?)",
        ("Team 1", "BW", "https://example.com/webhook1"),
    )
    temp_db.execute(
        "INSERT INTO tenants (name, location, webhook_url) VALUES (?, ?, ?)",
        ("Team 2", "BY", "https://example.com/webhook2"),
    )
    temp_db.commit()

    cursor = temp_db.execute("SELECT id FROM tenants ORDER BY id")
    ids = [row[0] for row in cursor.fetchall()]
    assert ids == [1, 2]


def test_tenant_name_index_exists(temp_db, schema_sql):
    """Test that an index exists on tenant name for performance."""
    temp_db.executescript(schema_sql)

    cursor = temp_db.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='tenants'"
    )
    indexes = [row[0] for row in cursor.fetchall()]

    # Check for index on name column (may be named differently)
    assert any("name" in idx.lower() for idx in indexes if idx), (
        "Index on name column should exist"
    )
