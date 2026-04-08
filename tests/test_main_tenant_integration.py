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
from unittest.mock import patch


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
        "INSERT INTO tenants (name, location, webhook_url, active) VALUES (?, ?, ?, ?)",
        ("Team Alpha", "BW", "https://example.com/alpha", 1),
    )
    conn.execute(
        "INSERT INTO tenants (name, location, webhook_url, active) VALUES (?, ?, ?, ?)",
        ("Team Beta", "BY", "https://example.com/beta", 1),
    )
    conn.execute(
        "INSERT INTO tenants (name, location, webhook_url, active) VALUES (?, ?, ?, ?)",
        ("Team Inactive", "BE", "https://example.com/inactive", 0),
    )
    # Create vacation table (needed by cleanup_old_vacations)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS vacation (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            start_date DATE NOT NULL,
            end_date DATE NOT NULL,
            FOREIGN KEY (user_id) REFERENCES user (id)
        )
    """)

    conn.commit()
    conn.close()

    return db_path


def test_main_with_specific_tenant(test_db_with_tenants):
    """Test main() processes specific tenant when --tenant is provided."""
    with (
        patch(
            "sys.argv", ["catcher.py", "--tenant", "Team Alpha", "--dry-run"]
        ),
        patch("catcher.DATABASE_PATH", str(test_db_with_tenants)),
        patch("catcher.process_tenant") as mock_process,
    ):
        mock_process.return_value = True

        from catcher import main

        main()

        # Should be called once for Team Alpha
        assert mock_process.call_count == 1
        call_args = mock_process.call_args
        assert call_args[0][1]["name"] == "Team Alpha"


def test_main_with_all_tenants(test_db_with_tenants):
    """Test main() processes all active tenants when --tenant not provided."""
    with (
        patch("sys.argv", ["catcher.py", "--dry-run"]),
        patch("catcher.DATABASE_PATH", str(test_db_with_tenants)),
        patch("catcher.process_tenant") as mock_process,
    ):
        mock_process.return_value = True

        from catcher import main

        main()

        # Should be called twice (Team Alpha and Team Beta, not Team Inactive)
        assert mock_process.call_count == 2
        tenant_names = [call[0][1]["name"] for call in mock_process.call_args_list]
        assert "Team Alpha" in tenant_names
        assert "Team Beta" in tenant_names
        assert "Team Inactive" not in tenant_names


def test_main_with_nonexistent_tenant(test_db_with_tenants, capsys):
    """Test main() exits with error when tenant not found."""
    with (
        patch("sys.argv", ["catcher.py", "--tenant", "NonExistent"]),
        patch("catcher.DATABASE_PATH", str(test_db_with_tenants)),
        pytest.raises(SystemExit),
    ):
        from catcher import main

        main()


def test_main_with_inactive_tenant(test_db_with_tenants, capsys):
    """Test main() exits with error when tenant is inactive."""
    with (
        patch("sys.argv", ["catcher.py", "--tenant", "Team Inactive"]),
        patch("catcher.DATABASE_PATH", str(test_db_with_tenants)),
        pytest.raises(SystemExit),
    ):
        from catcher import main

        main()


def test_main_continues_on_tenant_failure(test_db_with_tenants):
    """Test main() continues processing other tenants if one fails."""
    with (
        patch("sys.argv", ["catcher.py", "--dry-run"]),
        patch("catcher.DATABASE_PATH", str(test_db_with_tenants)),
        patch("catcher.process_tenant") as mock_process,
    ):
        # First tenant fails, second succeeds
        mock_process.side_effect = [False, True]

        from catcher import main

        main()

        # Should still call both tenants
        assert mock_process.call_count == 2


def test_main_logs_summary_for_multiple_tenants(test_db_with_tenants, caplog):
    """Test main() logs summary when processing multiple tenants."""
    with (
        patch("sys.argv", ["catcher.py", "--dry-run"]),
        patch("catcher.DATABASE_PATH", str(test_db_with_tenants)),
        patch("catcher.process_tenant") as mock_process,
    ):
        mock_process.return_value = True

        from catcher import main
        import logging

        with caplog.at_level(logging.INFO):
            main()

        # Check for summary log
        assert any(
            "Processing 2 active tenants" in record.message for record in caplog.records
        )
