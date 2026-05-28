-- Tenant table schema for multi-tenant support
-- Each tenant represents a team/department with its own users and configuration

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

-- Index on name for fast tenant lookups
CREATE INDEX IF NOT EXISTS idx_tenants_name ON tenants(name);

-- Index on active status for filtering active tenants
CREATE INDEX IF NOT EXISTS idx_tenants_active ON tenants(active);
