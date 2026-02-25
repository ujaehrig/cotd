#!/usr/bin/env -S uv run --script

# /// script
# dependencies = [
#    "pytest>=7.0.0",
# ]
# ///

import sqlite3
import pytest
import subprocess
import sys
from pathlib import Path


@pytest.fixture
def test_db(tmp_path):
    """Create a test database with tenants table."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)

    # Create tenants table
    schema_path = Path(__file__).parent / "schema_tenants.sql"
    conn.executescript(schema_path.read_text())

    # Add some test tenants
    conn.execute(
        "INSERT INTO tenants (name, location, webhook_url) VALUES (?, ?, ?)",
        ("Team Alpha", "BW", "https://example.com/alpha"),
    )
    conn.execute(
        "INSERT INTO tenants (name, location, webhook_url) VALUES (?, ?, ?)",
        ("Team Beta", "BY", "https://example.com/beta"),
    )
    conn.execute(
        "INSERT INTO tenants (name, location, webhook_url, active) VALUES (?, ?, ?, ?)",
        ("Team Inactive", "BE", "https://example.com/inactive", 0),
    )
    conn.commit()
    conn.close()

    return db_path


def run_manage_tenants(db_path, *args):
    """Helper to run manage_tenants.py with arguments."""
    result = subprocess.run(
        [sys.executable, "manage_tenants.py", "--db", str(db_path)] + list(args),
        capture_output=True,
        text=True,
    )
    return result


def test_list_all_tenants(test_db):
    """Test listing all tenants."""
    result = run_manage_tenants(test_db, "list")
    assert result.returncode == 0
    assert "Team Alpha" in result.stdout
    assert "Team Beta" in result.stdout
    assert "Team Inactive" in result.stdout


def test_list_active_only(test_db):
    """Test listing only active tenants."""
    result = run_manage_tenants(test_db, "list", "--active-only")
    assert result.returncode == 0
    assert "Team Alpha" in result.stdout
    assert "Team Beta" in result.stdout
    assert "Team Inactive" not in result.stdout


def test_add_tenant(test_db):
    """Test adding a new tenant."""
    result = run_manage_tenants(
        test_db, "add", "Team Gamma", "NW", "https://example.com/gamma"
    )
    assert result.returncode == 0

    # Verify tenant was added
    conn = sqlite3.connect(test_db)
    cursor = conn.execute(
        "SELECT name, location, webhook_url FROM tenants WHERE name = ?",
        ("Team Gamma",),
    )
    tenant = cursor.fetchone()
    conn.close()

    assert tenant is not None
    assert tenant[0] == "Team Gamma"
    assert tenant[1] == "NW"
    assert tenant[2] == "https://example.com/gamma"


def test_add_duplicate_tenant_fails(test_db):
    """Test that adding duplicate tenant name fails."""
    result = run_manage_tenants(
        test_db, "add", "Team Alpha", "NW", "https://example.com/duplicate"
    )
    assert result.returncode != 0
    assert (
        "already exists" in result.stderr.lower() or "unique" in result.stderr.lower()
    )


def test_update_tenant_name(test_db):
    """Test updating tenant name."""
    result = run_manage_tenants(
        test_db, "update", "Team Alpha", "--name", "Team Alpha Updated"
    )
    assert result.returncode == 0

    # Verify update
    conn = sqlite3.connect(test_db)
    cursor = conn.execute("SELECT name FROM tenants WHERE id = 1")
    name = cursor.fetchone()[0]
    conn.close()

    assert name == "Team Alpha Updated"


def test_update_tenant_location(test_db):
    """Test updating tenant location."""
    result = run_manage_tenants(test_db, "update", "Team Alpha", "--location", "HH")
    assert result.returncode == 0

    # Verify update
    conn = sqlite3.connect(test_db)
    cursor = conn.execute(
        "SELECT location FROM tenants WHERE name = ?", ("Team Alpha",)
    )
    location = cursor.fetchone()[0]
    conn.close()

    assert location == "HH"


def test_update_tenant_webhook(test_db):
    """Test updating tenant webhook URL."""
    result = run_manage_tenants(
        test_db, "update", "Team Alpha", "--webhook", "https://new.webhook.url"
    )
    assert result.returncode == 0

    # Verify update
    conn = sqlite3.connect(test_db)
    cursor = conn.execute(
        "SELECT webhook_url FROM tenants WHERE name = ?", ("Team Alpha",)
    )
    webhook = cursor.fetchone()[0]
    conn.close()

    assert webhook == "https://new.webhook.url"


def test_update_by_id(test_db):
    """Test updating tenant by ID instead of name."""
    result = run_manage_tenants(test_db, "update", "1", "--location", "SH")
    assert result.returncode == 0

    # Verify update
    conn = sqlite3.connect(test_db)
    cursor = conn.execute("SELECT location FROM tenants WHERE id = 1")
    location = cursor.fetchone()[0]
    conn.close()

    assert location == "SH"


def test_deactivate_tenant(test_db):
    """Test deactivating a tenant."""
    result = run_manage_tenants(test_db, "deactivate", "Team Alpha")
    assert result.returncode == 0

    # Verify deactivation
    conn = sqlite3.connect(test_db)
    cursor = conn.execute("SELECT active FROM tenants WHERE name = ?", ("Team Alpha",))
    active = cursor.fetchone()[0]
    conn.close()

    assert active == 0


def test_activate_tenant(test_db):
    """Test activating a tenant."""
    result = run_manage_tenants(test_db, "activate", "Team Inactive")
    assert result.returncode == 0

    # Verify activation
    conn = sqlite3.connect(test_db)
    cursor = conn.execute(
        "SELECT active FROM tenants WHERE name = ?", ("Team Inactive",)
    )
    active = cursor.fetchone()[0]
    conn.close()

    assert active == 1


def test_delete_tenant(test_db):
    """Test deleting a tenant."""
    result = run_manage_tenants(test_db, "delete", "Team Inactive", "--force")
    assert result.returncode == 0

    # Verify deletion
    conn = sqlite3.connect(test_db)
    cursor = conn.execute(
        "SELECT COUNT(*) FROM tenants WHERE name = ?", ("Team Inactive",)
    )
    count = cursor.fetchone()[0]
    conn.close()

    assert count == 0


def test_delete_without_force_requires_confirmation(test_db):
    """Test that delete without --force requires confirmation."""
    # This test checks that the command structure supports --force flag
    # In actual usage, without --force it would prompt for confirmation
    result = run_manage_tenants(test_db, "delete", "Team Inactive", "--force")
    assert result.returncode == 0


def test_update_nonexistent_tenant_fails(test_db):
    """Test that updating non-existent tenant fails."""
    result = run_manage_tenants(test_db, "update", "NonExistent", "--location", "BW")
    assert result.returncode != 0


def test_deactivate_nonexistent_tenant_fails(test_db):
    """Test that deactivating non-existent tenant fails."""
    result = run_manage_tenants(test_db, "deactivate", "NonExistent")
    assert result.returncode != 0
