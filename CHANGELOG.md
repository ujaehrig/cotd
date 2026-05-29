# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

## [2026-05-29b] - SQLite Concurrency

### Added

- WAL journal mode for concurrent access from catcher and takeover app
- `busy_timeout` (5s) to handle simultaneous writes gracefully

## [2026-05-29] - Slack Channel ID per Tenant

### Added

- Tenant-specific `slack_channel_id` sent in webhook payload
- Migration script `migrate_channel_id.py`
- `--channel-id` option in `manage_tenants.py update`
- Long mode (`-l`) for `manage_tenants.py list`
- CHANGELOG.md

### Changed

- Notifications are skipped for tenants without `slack_channel_id`
  configured

### Fixed

- Takeover app: strip leading `@` from Slack usernames

## [2026-05-28] - Catcher Takeover

### Added

- Catcher takeover via HMAC-signed registration URL
- Takeover web app (`takeover_app.py`) with Flask
- One takeover per tenant per day limit
- User matching by email, email prefix, or display name
- `takeover_log` table for audit trail
- Automatic cleanup of old takeover log entries
- Dockerfile for running the takeover app
- Migration script `migrate_takeover.py`

## [2026-04-09] - Bug Fix

### Fixed

- Tenant-filtered query in `get_last_working_day_catcher`

## [2026-04-08] - Cleanup and Refactoring

### Changed

- Moved test files to `tests/` folder
- Added `.coverage` to `.gitignore`

### Fixed

- Added migrate upsert script for vacation sync

## [2026-04-05] - Code Review and UI Removal

### Removed

- Flask web UI (authentication, vacation management pages)
- Replaced with CLI-only management

### Added

- `db.py` as single source of truth for database connections
- `--tenant` flag to `user_statistics.py`
- Per-tenant user display in statistics

### Fixed

- Security-related issues from code review
- Deprecated function calls

## [2026-03-31] - iCal Vacation Sync

### Added

- Automatic vacation sync from iCal/ICS calendar feeds
- Fuzzy name matching for calendar events
- Confluence-specific calendar parsing
- User statistics script
- Holiday detection in vacation sync
- Cleanup of old vacation entries

## [2026-02-24] - Multi-Tenant and Weighted Selection

### Added

- Multi-tenant support with independent team management
- Weighted selection algorithm with fairness guarantees
- Non-linear weight calculation
- Historical balance factor
- Consecutive day prevention across weekends/holidays
- `--force-notify` command line parameter
- `--dry-run` mode for safe testing
- Configurable logging via `.env`
- Holiday detection fallback (web service + library)
- Configurable holiday region

### Changed

- Unified configuration via environment variables
- Increased history retention to 1 year

## [2025-10-28] - Vacation Management

### Added

- Flask web UI with authentication
- Vacation management with overlap/duplicate validation
- HTMX-based dynamic forms
- Vacation webhook notifications
- Docker deployment support
- PEP 723 script metadata for dependency management

## [2025-03-18] - Initial Python Migration

### Added

- Migrated from shell script to Python
- Slack notification with retry mechanism
- SQLite database for user and vacation tracking
- `.env` configuration via python-dotenv
- `uv` as package manager

### Removed

- Original `catcher.sh` shell script
