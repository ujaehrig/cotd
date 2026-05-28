"""Tests for generate_registration_url and takeover_app."""

import datetime
import hashlib
import hmac
import sqlite3

import pytest
from pathlib import Path
from unittest.mock import patch

from catcher import generate_registration_url


@pytest.fixture
def db(tmp_path):
    """Create test database with schema."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    schema_path = Path(__file__).parent.parent / "schema.sql"
    conn.executescript(schema_path.read_text())
    conn.execute(
        "INSERT INTO tenants (id, name, location, webhook_url, active, takeover_secret) "
        "VALUES (1, 'Team A', 'BW', 'http://hook', 1, 'testsecret')"
    )
    conn.execute(
        "INSERT INTO user (id, mail, weekdays, tenant_id) VALUES (1, 'alice@example.com', '0123456', 1)"
    )
    conn.execute(
        "INSERT INTO user (id, mail, weekdays, tenant_id, display_name) "
        "VALUES (2, 'bob.smith@example.com', '0123456', 1, 'bobby')"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS takeover_log "
        "(id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id INTEGER NOT NULL, "
        "takeover_date DATE NOT NULL, new_user_id INTEGER NOT NULL)"
    )
    conn.commit()
    conn.close()
    return db_path


class TestGenerateRegistrationUrl:
    @patch("catcher.TAKEOVER_BASE_URL", "https://cotd.example.com")
    def test_generates_valid_url(self):
        url = generate_registration_url(1, "mysecret")
        assert url.startswith("https://cotd.example.com/takeover?tenant=1&nonce=")
        # Verify nonce
        nonce = url.split("nonce=")[1]
        today = datetime.date.today().isoformat()
        expected = hmac.new(
            "mysecret".encode(), f"1{today}".encode(), hashlib.sha256
        ).hexdigest()
        assert nonce == expected

    @patch("catcher.TAKEOVER_BASE_URL", "")
    def test_returns_empty_when_no_base_url(self):
        assert generate_registration_url(1, "mysecret") == ""

    @patch("catcher.TAKEOVER_BASE_URL", "https://cotd.example.com")
    def test_returns_empty_when_no_secret(self):
        assert generate_registration_url(1, "") == ""

    @patch("catcher.TAKEOVER_BASE_URL", "https://cotd.example.com")
    def test_different_tenants_produce_different_nonces(self):
        url1 = generate_registration_url(1, "secret")
        url2 = generate_registration_url(2, "secret")
        assert url1.split("nonce=")[1] != url2.split("nonce=")[1]


class TestTakeoverApp:
    @pytest.fixture
    def client(self, db):
        with patch("takeover_app.DATABASE_PATH", str(db)):
            from takeover_app import app

            app.config["TESTING"] = True
            with app.test_client() as client:
                yield client

    def _make_nonce(self, tenant_id, secret):
        today = datetime.date.today().isoformat()
        return hmac.new(
            secret.encode(), f"{tenant_id}{today}".encode(), hashlib.sha256
        ).hexdigest()

    def test_missing_params_returns_400(self, client):
        resp = client.get("/takeover")
        assert resp.status_code == 400

    def test_invalid_nonce_returns_403(self, client):
        resp = client.get("/takeover?tenant=1&nonce=bad&uid=alice@example.com")
        assert resp.status_code == 403

    def test_valid_takeover_by_email(self, client, db):
        nonce = self._make_nonce("1", "testsecret")
        resp = client.get(f"/takeover?tenant=1&nonce={nonce}&uid=alice@example.com")
        assert resp.status_code == 200
        assert "Thank you" in resp.data.decode()

        # Verify DB state
        conn = sqlite3.connect(db)
        row = conn.execute(
            "SELECT user_id FROM selection_history WHERE selected_date = ?",
            (datetime.date.today().isoformat(),),
        ).fetchone()
        assert row[0] == 1
        conn.close()

    def test_valid_takeover_by_email_prefix(self, client, db):
        nonce = self._make_nonce("1", "testsecret")
        resp = client.get(f"/takeover?tenant=1&nonce={nonce}&uid=bob.smith")
        assert resp.status_code == 200

        conn = sqlite3.connect(db)
        row = conn.execute(
            "SELECT user_id FROM selection_history WHERE selected_date = ?",
            (datetime.date.today().isoformat(),),
        ).fetchone()
        assert row[0] == 2
        conn.close()

    def test_valid_takeover_by_display_name(self, client, db):
        nonce = self._make_nonce("1", "testsecret")
        resp = client.get(f"/takeover?tenant=1&nonce={nonce}&uid=bobby")
        assert resp.status_code == 200

        conn = sqlite3.connect(db)
        row = conn.execute(
            "SELECT user_id FROM selection_history WHERE selected_date = ?",
            (datetime.date.today().isoformat(),),
        ).fetchone()
        assert row[0] == 2
        conn.close()

    def test_unknown_user_returns_404(self, client):
        nonce = self._make_nonce("1", "testsecret")
        resp = client.get(f"/takeover?tenant=1&nonce={nonce}&uid=nobody")
        assert resp.status_code == 404

    def test_uid_with_leading_at_sign(self, client, db):
        nonce = self._make_nonce("1", "testsecret")
        resp = client.get(f"/takeover?tenant=1&nonce={nonce}&uid=@bob.smith")
        assert resp.status_code == 200

        conn = sqlite3.connect(db)
        row = conn.execute(
            "SELECT user_id FROM selection_history WHERE selected_date = ?",
            (datetime.date.today().isoformat(),),
        ).fetchone()
        assert row[0] == 2
        conn.close()

    def test_takeover_resets_previous_catcher(self, client, db):
        today = datetime.date.today().isoformat()
        yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()

        # Set up: alice was selected today, had a prior selection yesterday
        conn = sqlite3.connect(db)
        conn.execute(
            "INSERT INTO selection_history (user_id, selected_date) VALUES (1, ?)",
            (yesterday,),
        )
        conn.execute(
            "INSERT INTO selection_history (user_id, selected_date) VALUES (1, ?)",
            (today,),
        )
        conn.execute("UPDATE user SET last_chosen = ? WHERE id = 1", (today,))
        conn.commit()
        conn.close()

        # Bob takes over
        nonce = self._make_nonce("1", "testsecret")
        resp = client.get(f"/takeover?tenant=1&nonce={nonce}&uid=bob.smith")
        assert resp.status_code == 200

        # Verify alice's last_chosen was reset to yesterday
        conn = sqlite3.connect(db)
        alice = conn.execute("SELECT last_chosen FROM user WHERE id = 1").fetchone()
        assert alice[0] == yesterday
        # Bob is now today's catcher
        bob = conn.execute("SELECT last_chosen FROM user WHERE id = 2").fetchone()
        assert bob[0] == today
        conn.close()

    def test_second_takeover_same_day_returns_409(self, client, db):
        nonce = self._make_nonce("1", "testsecret")
        # First takeover succeeds
        resp = client.get(f"/takeover?tenant=1&nonce={nonce}&uid=alice@example.com")
        assert resp.status_code == 200
        # Second takeover by different user is rejected
        resp = client.get(f"/takeover?tenant=1&nonce={nonce}&uid=bob.smith")
        assert resp.status_code == 409

    def test_same_user_clicking_again_is_idempotent(self, client, db):
        nonce = self._make_nonce("1", "testsecret")
        resp = client.get(f"/takeover?tenant=1&nonce={nonce}&uid=alice@example.com")
        assert resp.status_code == 200
        # Same user clicking again gets success (idempotent)
        resp = client.get(f"/takeover?tenant=1&nonce={nonce}&uid=alice@example.com")
        assert resp.status_code == 200
        assert "Thank you" in resp.data.decode()

    def test_expired_nonce_from_yesterday_returns_403(self, client):
        yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
        old_nonce = hmac.new(
            "testsecret".encode(), f"1{yesterday}".encode(), hashlib.sha256
        ).hexdigest()
        resp = client.get(
            f"/takeover?tenant=1&nonce={old_nonce}&uid=alice@example.com"
        )
        assert resp.status_code == 403


class TestCleanupOldTakeoverLog:
    @pytest.fixture
    def db_with_takeover_log(self, tmp_path):
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(db_path)
        conn.execute(
            "CREATE TABLE takeover_log "
            "(id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id INTEGER NOT NULL, "
            "takeover_date DATE NOT NULL, new_user_id INTEGER NOT NULL)"
        )
        # Insert old and recent records
        old_date = (datetime.date.today() - datetime.timedelta(days=400)).isoformat()
        recent_date = (datetime.date.today() - datetime.timedelta(days=30)).isoformat()
        conn.execute(
            "INSERT INTO takeover_log (tenant_id, takeover_date, new_user_id) VALUES (1, ?, 1)",
            (old_date,),
        )
        conn.execute(
            "INSERT INTO takeover_log (tenant_id, takeover_date, new_user_id) VALUES (1, ?, 2)",
            (recent_date,),
        )
        conn.commit()
        return conn

    def test_deletes_old_records(self, db_with_takeover_log):
        from cleanup import cleanup_old_takeover_log

        deleted = cleanup_old_takeover_log(db_with_takeover_log, retention_days=365)
        assert deleted == 1
        count = db_with_takeover_log.execute(
            "SELECT COUNT(*) FROM takeover_log"
        ).fetchone()[0]
        assert count == 1

    def test_dry_run_does_not_delete(self, db_with_takeover_log):
        from cleanup import cleanup_old_takeover_log

        deleted = cleanup_old_takeover_log(
            db_with_takeover_log, retention_days=365, dry_run=True
        )
        assert deleted == 1
        count = db_with_takeover_log.execute(
            "SELECT COUNT(*) FROM takeover_log"
        ).fetchone()[0]
        assert count == 2

    def test_nothing_to_delete(self, db_with_takeover_log):
        from cleanup import cleanup_old_takeover_log

        deleted = cleanup_old_takeover_log(db_with_takeover_log, retention_days=500)
        assert deleted == 0
