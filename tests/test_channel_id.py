"""Tests for slack_channel_id feature."""

import sqlite3

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from catcher import (
    get_tenant_by_name,
    get_active_tenants,
    trigger_slack,
    process_tenant,
)


@pytest.fixture
def db(tmp_path):
    """Create test database with schema including slack_channel_id."""
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
            source VARCHAR(20) DEFAULT 'manual',
            last_synced TIMESTAMP,
            ical_event_uid VARCHAR(200),
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
    conn.execute(
        "INSERT INTO tenants (id, name, location, webhook_url, active, slack_channel_id) "
        "VALUES (1, 'Team Alpha', 'BW', 'https://hooks.slack.com/test', 1, 'C12345')"
    )
    conn.execute(
        "INSERT INTO tenants (id, name, location, webhook_url, active, slack_channel_id) "
        "VALUES (2, 'Team Beta', 'BY', 'https://hooks.slack.com/test2', 1, NULL)"
    )
    conn.execute(
        "INSERT INTO user (id, mail, weekdays, tenant_id) "
        "VALUES (1, 'alice@example.com', '0123456', 1)"
    )
    conn.commit()
    return conn


class TestTenantChannelId:
    def test_get_tenant_by_name_includes_channel_id(self, db):
        tenant = get_tenant_by_name(db, "Team Alpha")
        assert tenant["slack_channel_id"] == "C12345"

    def test_get_tenant_by_name_channel_id_null(self, db):
        tenant = get_tenant_by_name(db, "Team Beta")
        assert tenant["slack_channel_id"] is None

    def test_get_active_tenants_includes_channel_id(self, db):
        tenants = get_active_tenants(db)
        assert tenants[0]["slack_channel_id"] == "C12345"
        assert tenants[1]["slack_channel_id"] is None


class TestTriggerSlackChannelId:
    @patch("catcher.requests.post")
    def test_payload_includes_channel_id(self, mock_post):
        mock_post.return_value = MagicMock(status_code=200)
        trigger_slack(
            "alice@example.com",
            webhook_url="https://hooks.slack.com/test",
            registration_url="https://example.com/takeover?nonce=abc",
            channel_id="C12345",
        )
        call_args = mock_post.call_args
        import json

        payload = json.loads(call_args.kwargs.get("data") or call_args[1]["data"])
        assert payload["channel_id"] == "C12345"

    @patch("catcher.requests.post")
    def test_payload_without_channel_id(self, mock_post):
        mock_post.return_value = MagicMock(status_code=200)
        trigger_slack(
            "alice@example.com",
            webhook_url="https://hooks.slack.com/test",
        )
        call_args = mock_post.call_args
        import json

        payload = json.loads(call_args.kwargs.get("data") or call_args[1]["data"])
        assert payload["channel_id"] == ""


class TestProcessTenantChannelId:
    @patch("catcher.trigger_slack")
    @patch("catcher.is_weekend", return_value=False)
    @patch("catcher.is_holiday", return_value=False)
    def test_skips_notification_when_channel_id_missing(
        self, mock_holiday, mock_weekend, mock_trigger, db
    ):
        tenant = get_tenant_by_name(db, "Team Beta")
        process_tenant(db, tenant)
        mock_trigger.assert_not_called()

    @patch("catcher.trigger_slack", return_value=True)
    @patch("catcher.is_weekend", return_value=False)
    @patch("catcher.is_holiday", return_value=False)
    def test_sends_notification_when_channel_id_present(
        self, mock_holiday, mock_weekend, mock_trigger, db
    ):
        tenant = get_tenant_by_name(db, "Team Alpha")
        process_tenant(db, tenant)
        mock_trigger.assert_called_once()
        call_kwargs = mock_trigger.call_args.kwargs
        assert call_kwargs.get("channel_id") == "C12345"
