-- Catcher Of The Day - Complete Database Schema
-- Use this for fresh installations: sqlite3 user.db < schema.sql

CREATE TABLE IF NOT EXISTS tenants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) UNIQUE NOT NULL,
    location VARCHAR(10) NOT NULL,
    webhook_url VARCHAR(500) NOT NULL,
    active BOOLEAN DEFAULT 1,
    ical_url VARCHAR(500),
    takeover_secret VARCHAR(200),
    slack_channel_id VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

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
    FOREIGN KEY (user_id) REFERENCES user(id),
    UNIQUE (user_id, ical_event_uid)
);

CREATE TABLE IF NOT EXISTS selection_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    selected_date DATE NOT NULL,
    tenant_id INTEGER NOT NULL,
    FOREIGN KEY (user_id) REFERENCES user(id),
    FOREIGN KEY (tenant_id) REFERENCES tenants(id)
);

CREATE TABLE IF NOT EXISTS vacation_sync_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL,
    sync_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20),
    events_processed INTEGER DEFAULT 0,
    users_matched INTEGER DEFAULT 0,
    error_message TEXT,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_tenants_name ON tenants(name);
CREATE INDEX IF NOT EXISTS idx_tenants_active ON tenants(active);
CREATE INDEX IF NOT EXISTS idx_user_tenant ON user(tenant_id);
CREATE INDEX IF NOT EXISTS idx_vacation_user ON vacation(user_id);
CREATE INDEX IF NOT EXISTS idx_vacation_dates
    ON vacation(start_date, end_date);
CREATE INDEX IF NOT EXISTS idx_selection_history_date
    ON selection_history(selected_date);
CREATE INDEX IF NOT EXISTS idx_selection_history_user
    ON selection_history(user_id);
CREATE INDEX IF NOT EXISTS idx_selection_history_tenant_date
    ON selection_history(tenant_id, selected_date);
