"""Tests for selection_history tenant_id feature and manage_users move command."""

import datetime
import sqlite3

import pytest
from pathlib import Path
from unittest.mock import patch

from catcher import (
    get_recent_selection_count,
    get_last_working_day_catcher,
)


@pytest.fixture
def multi_tenant_db(tmp_path):
    """Create a DB with two tenants and users, plus selection_history with tenant_id."""
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

    # Two tenants
    conn.execute(
        "INSERT INTO tenants (id, name, location, webhook_url, active) "
        "VALUES (1, 'Small Team', 'BW', 'http://hook1', 1)"
    )
    conn.execute(
        "INSERT INTO tenants (id, name, location, webhook_url, active) "
        "VALUES (2, 'Big Team', 'BY', 'http://hook2', 1)"
    )

    # Alice in Small Team, Bob and Carol in Big Team (all available every day)
    conn.execute(
        "INSERT INTO user (id, mail, weekdays, tenant_id) VALUES (1, 'alice@example.com', '0,1,2,3,4,5,6', 1)"
    )
    conn.execute(
        "INSERT INTO user (id, mail, weekdays, tenant_id) VALUES (2, 'bob@example.com', '0,1,2,3,4,5,6', 2)"
    )
    conn.execute(
        "INSERT INTO user (id, mail, weekdays, tenant_id) VALUES (3, 'carol@example.com', '0,1,2,3,4,5,6', 2)"
    )

    conn.commit()
    yield conn
    conn.close()


class TestFairnessIsolation:
    """Test that selection_history.tenant_id properly isolates fairness calculations."""

    def test_old_tenant_history_ignored_after_move(self, multi_tenant_db):
        """A user moved from tenant 1 to tenant 2 should have their tenant-1 history ignored."""
        conn = multi_tenant_db

        # Alice was selected many times in Small Team
        for i in range(20):
            date = (datetime.date.today() - datetime.timedelta(days=i + 1)).isoformat()
            conn.execute(
                "INSERT INTO selection_history (user_id, selected_date, tenant_id) VALUES (1, ?, 1)",
                (date,),
            )
        conn.commit()

        # Move Alice to Big Team
        conn.execute("UPDATE user SET tenant_id = 2 WHERE id = 1")
        conn.commit()

        # Alice's recent selection count for Big Team should be 0
        count = get_recent_selection_count(conn, 1, tenant_id=2)
        assert count == 0

    def test_total_selections_scoped_to_current_tenant(self, multi_tenant_db):
        """Total selections should only count entries for the current tenant."""
        conn = multi_tenant_db

        # Alice has 10 selections in tenant 1 and 2 in tenant 2
        for i in range(10):
            date = (datetime.date.today() - datetime.timedelta(days=i + 1)).isoformat()
            conn.execute(
                "INSERT INTO selection_history (user_id, selected_date, tenant_id) VALUES (1, ?, 1)",
                (date,),
            )
        for i in range(2):
            date = (datetime.date.today() - datetime.timedelta(days=i + 11)).isoformat()
            conn.execute(
                "INSERT INTO selection_history (user_id, selected_date, tenant_id) VALUES (1, ?, 2)",
                (date,),
            )
        conn.commit()

        # Move Alice to Big Team
        conn.execute("UPDATE user SET tenant_id = 2 WHERE id = 1")
        conn.commit()

        # Only 2 selections count for tenant 2
        count = get_recent_selection_count(conn, 1, tenant_id=2, days=365)
        assert count == 2

    def test_get_last_working_day_catcher_uses_tenant_id(self, multi_tenant_db):
        """get_last_working_day_catcher should use selection_history.tenant_id."""
        conn = multi_tenant_db
        yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()

        # Alice was catcher yesterday for tenant 1
        conn.execute(
            "INSERT INTO selection_history (user_id, selected_date, tenant_id) VALUES (1, ?, 1)",
            (yesterday,),
        )
        # Bob was catcher yesterday for tenant 2
        conn.execute(
            "INSERT INTO selection_history (user_id, selected_date, tenant_id) VALUES (2, ?, 2)",
            (yesterday,),
        )
        conn.commit()

        # Even if yesterday is a weekend day, test the concept
        with patch("catcher.holidays.Germany") as mock_holidays:
            mock_holidays.return_value = {}
            last_t1 = get_last_working_day_catcher(conn, tenant_id=1)
            last_t2 = get_last_working_day_catcher(conn, tenant_id=2)

        # If yesterday was a weekday, these should be correct
        # (if weekend, both will be None which is also valid)
        if datetime.date.today().weekday() not in (0, 6):
            # yesterday was not weekend (today is not Mon or Sun)
            assert last_t1 == 1
            assert last_t2 == 2


class TestMoveBackHistory:
    """Test that moving back to a previous tenant restores history context."""

    def test_history_restored_on_move_back(self, multi_tenant_db):
        """When a user moves A→B→A, their tenant-A history is visible again."""
        conn = multi_tenant_db

        # Alice has history in tenant 1
        for i in range(5):
            date = (datetime.date.today() - datetime.timedelta(days=i + 1)).isoformat()
            conn.execute(
                "INSERT INTO selection_history (user_id, selected_date, tenant_id) VALUES (1, ?, 1)",
                (date,),
            )
        conn.commit()

        # Move to tenant 2 — no history there
        conn.execute("UPDATE user SET tenant_id = 2 WHERE id = 1")
        conn.commit()
        count_in_2 = get_recent_selection_count(conn, 1, tenant_id=2)
        assert count_in_2 == 0

        # Move back to tenant 1 — history is back
        conn.execute("UPDATE user SET tenant_id = 1 WHERE id = 1")
        conn.commit()
        count_in_1 = get_recent_selection_count(conn, 1, tenant_id=1)
        assert count_in_1 == 5


class TestMigration:
    """Test the migration script logic."""

    def test_migration_adds_tenant_id_and_drops_last_chosen(self, tmp_path):
        """Test that migration adds tenant_id, backfills, and drops last_chosen."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(db_path)

        # Create pre-migration schema
        schema_path = Path(__file__).parent.parent / "schema_tenants.sql"
        conn.executescript(schema_path.read_text())
        conn.executescript("""
            CREATE TABLE user (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mail VARCHAR(50) UNIQUE NOT NULL,
                weekdays VARCHAR(10),
                last_chosen DATE,
                tenant_id INTEGER REFERENCES tenants(id)
            );
            CREATE TABLE selection_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                selected_date DATE NOT NULL,
                FOREIGN KEY (user_id) REFERENCES user(id)
            );
        """)
        conn.execute(
            "INSERT INTO tenants (id, name, location, webhook_url, active) "
            "VALUES (1, 'Team A', 'BW', 'http://hook', 1)"
        )
        conn.execute(
            "INSERT INTO user (id, mail, weekdays, last_chosen, tenant_id) "
            "VALUES (1, 'a@b.com', '1,2,3', '2026-01-01', 1)"
        )
        conn.execute(
            "INSERT INTO selection_history (user_id, selected_date) VALUES (1, '2026-01-01')"
        )
        conn.commit()
        conn.close()

        # Run migration
        with (
            patch("migrate_selection_history_tenant.DATABASE_PATH", str(db_path)),
            patch("db.DATABASE_PATH", str(db_path)),
        ):
            from migrate_selection_history_tenant import main

            main()

        # Verify result
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        # tenant_id is backfilled
        row = conn.execute(
            "SELECT tenant_id FROM selection_history WHERE id = 1"
        ).fetchone()
        assert row["tenant_id"] == 1

        # last_chosen is gone
        cols = [r[1] for r in conn.execute("PRAGMA table_info(user)").fetchall()]
        assert "last_chosen" not in cols

        # Index exists
        indexes = [
            r[1]
            for r in conn.execute(
                "SELECT * FROM sqlite_master WHERE type='index' AND tbl_name='selection_history'"
            ).fetchall()
        ]
        assert "idx_selection_history_tenant_date" in indexes

        conn.close()

    def test_migration_is_idempotent(self, tmp_path):
        """Running migration twice should not error."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(db_path)

        schema_path = Path(__file__).parent.parent / "schema_tenants.sql"
        conn.executescript(schema_path.read_text())
        conn.executescript("""
            CREATE TABLE user (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mail VARCHAR(50) UNIQUE NOT NULL,
                weekdays VARCHAR(10),
                last_chosen DATE,
                tenant_id INTEGER REFERENCES tenants(id)
            );
            CREATE TABLE selection_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                selected_date DATE NOT NULL,
                FOREIGN KEY (user_id) REFERENCES user(id)
            );
        """)
        conn.execute(
            "INSERT INTO tenants (id, name, location, webhook_url, active) "
            "VALUES (1, 'Team A', 'BW', 'http://hook', 1)"
        )
        conn.execute(
            "INSERT INTO user (id, mail, weekdays, tenant_id) "
            "VALUES (1, 'a@b.com', '1,2,3', 1)"
        )
        conn.commit()
        conn.close()

        with (
            patch("migrate_selection_history_tenant.DATABASE_PATH", str(db_path)),
            patch("db.DATABASE_PATH", str(db_path)),
        ):
            from migrate_selection_history_tenant import main

            main()
            # Second run should not raise
            main()

        conn = sqlite3.connect(db_path)
        cols = [r[1] for r in conn.execute("PRAGMA table_info(user)").fetchall()]
        assert "last_chosen" not in cols
        conn.close()


class TestManageUsersMove:
    """Test the move command in manage_users.py."""

    @pytest.fixture
    def move_db(self, tmp_path):
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE tenants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(100) UNIQUE NOT NULL,
                location VARCHAR(10) NOT NULL,
                webhook_url VARCHAR(500) NOT NULL,
                active BOOLEAN DEFAULT 1
            )
        """)
        conn.execute("""
            CREATE TABLE user (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mail VARCHAR(50) UNIQUE NOT NULL,
                weekdays VARCHAR(10),
                tenant_id INTEGER REFERENCES tenants(id),
                display_name VARCHAR(100)
            )
        """)
        conn.execute(
            "INSERT INTO tenants (id, name, location, webhook_url) VALUES (1, 'Team A', 'BW', 'http://a')"
        )
        conn.execute(
            "INSERT INTO tenants (id, name, location, webhook_url) VALUES (2, 'Team B', 'BY', 'http://b')"
        )
        conn.execute(
            "INSERT INTO user (id, mail, weekdays, tenant_id) VALUES (1, 'alice@example.com', '1,2,3,4,5', 1)"
        )
        conn.commit()
        conn.close()
        return db_path

    def test_move_user_to_new_tenant(self, move_db, capsys):
        from manage_users import cmd_move
        import argparse

        args = argparse.Namespace(
            identifier="alice@example.com", tenant="Team B", db=str(move_db)
        )
        cmd_move(args)

        conn = sqlite3.connect(move_db)
        row = conn.execute("SELECT tenant_id FROM user WHERE id = 1").fetchone()
        assert row[0] == 2
        conn.close()

        output = capsys.readouterr().out
        assert "Team A" in output
        assert "Team B" in output

    def test_move_user_already_in_tenant(self, move_db, capsys):
        from manage_users import cmd_move
        import argparse

        args = argparse.Namespace(
            identifier="alice@example.com", tenant="Team A", db=str(move_db)
        )
        cmd_move(args)

        output = capsys.readouterr().out
        assert "already in tenant" in output

    def test_move_user_not_found(self, move_db):
        from manage_users import cmd_move
        import argparse

        args = argparse.Namespace(
            identifier="nobody@example.com", tenant="Team B", db=str(move_db)
        )
        with pytest.raises(SystemExit):
            cmd_move(args)

    def test_move_tenant_not_found(self, move_db):
        from manage_users import cmd_move
        import argparse

        args = argparse.Namespace(
            identifier="alice@example.com", tenant="Nonexistent", db=str(move_db)
        )
        with pytest.raises(SystemExit):
            cmd_move(args)
