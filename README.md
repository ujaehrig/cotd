# Catcher Of The Day

Simple script to trigger a workflow in Slack, which will show a catcher
of the day.

You need to set up the workflow in Slack via the workflow builder.
Choose a webhook as trigger.

The script will call the triggering webhook and send an email address
as parameter. The email address is chosen from the database using an
advanced weighted selection algorithm that ensures fairness while
avoiding consecutive day assignments when possible.

The script will also take vacation times and holidays into
consideration. Old vacation entries are automatically cleaned up
(default: 90 days retention).

## Multi-Tenant Support

The application supports multiple tenants (teams/departments), each
with:

- Their own users and selection history
- Separate Slack webhook URLs for notifications
- Different holiday regions (German states)
- Independent catcher selection

### Running with Multiple Tenants

```bash
# Process all active tenants (default)
uv run catcher.py

# Process specific tenant
uv run catcher.py --tenant "Team Alpha"

# Dry run for specific tenant
uv run catcher.py --tenant "Team Alpha" --dry-run
```

### Managing Tenants

```bash
# List all tenants
uv run manage_tenants.py list

# Add a new tenant
uv run manage_tenants.py add "Team Beta" "BY" \
  "https://hooks.slack.com/workflows/..."

# Update tenant
uv run manage_tenants.py update "Team Beta" --location "BW"

# Update tenant with iCal URL
uv run manage_tenants.py update "Team Beta" \
  --ical-url "https://calendar.example.com/ical/team-beta.ics"

# Test iCal sync for a tenant
uv run manage_tenants.py test-sync "Team Beta"

# View sync status and logs
uv run manage_tenants.py sync-status "Team Beta"

# Deactivate/activate tenant
uv run manage_tenants.py deactivate "Team Beta"
uv run manage_tenants.py activate "Team Beta"
```

## Automatic Vacation Sync via iCal

The system supports automatic vacation synchronization from iCal/ICS
calendar feeds. This eliminates the need for manual vacation entry.

### How It Works

1. Each tenant can have an iCal feed URL configured
2. Before each catcher selection, the system automatically fetches
   and parses the calendar
3. Vacation events are matched to users using fuzzy name matching
4. The vacation database is updated automatically
5. If the calendar is unreachable, cached vacation data is used as
   fallback

### Setting Up iCal Sync

1. Get your calendar's iCal URL (Google Calendar, Outlook, etc.)
2. Configure the tenant:

   ```bash
   uv run manage_tenants.py update "Team Name" \
     --ical-url "https://calendar.example.com/ical/feed.ics"
   ```

3. Test the sync:

   ```bash
   uv run manage_tenants.py test-sync "Team Name"
   ```

4. Optionally set display names for better matching:

   ```bash
   uv run manage_users.py set-display-name \
     "john.doe@example.com" "Johnny"
   ```

### Calendar Event Format

The system extracts names from calendar event titles using fuzzy
matching. Supported formats include:

- "Vacation - John Doe"
- "OOO: Jane Smith"
- "John - Urlaub"
- "Out of office Victoria"

### Configuration Options

Add these to your `.env` file:

```bash
ICAL_SYNC_TIMEOUT=10
FUZZY_MATCH_THRESHOLD=80
ICAL_CACHE_RETENTION_HOURS=24
```

## Managing Users

```bash
# List all users
uv run manage_users.py list

# List users for specific tenant
uv run manage_users.py list --tenant "Team Name"

# Add a new user (tenant is required)
uv run manage_users.py add "john.doe@example.com" "Team Name"

# Add user with optional parameters
uv run manage_users.py add "john.doe@example.com" "Team Name" \
  --weekdays "0,1,2,3,4" --display-name "Johnny"

# Update user details
uv run manage_users.py update "john.doe@example.com" \
  --weekdays "0,1,2"

# Set display name for iCal matching
uv run manage_users.py set-display-name \
  "john.doe@example.com" "Johnny"

# Delete a user
uv run manage_users.py delete "john.doe@example.com"
```

## Managing Vacation Periods

```bash
# List all users
uv run manage_vacations.py list-users

# List all vacation periods
uv run manage_vacations.py list-vacations

# List vacation periods for a specific user
uv run manage_vacations.py list-vacations --user john@example.com

# Add a vacation period
uv run manage_vacations.py add john@example.com 2025-07-15 2025-07-30

# Add a single day vacation
uv run manage_vacations.py add john@example.com 2025-07-15

# Delete a vacation period
uv run manage_vacations.py delete 5
```

## Selection Algorithm

The system uses a sophisticated weighted selection algorithm that:

- Ensures fair distribution of duties over time
- Avoids consecutive day assignments when alternatives exist
- Balances workload based on recent selection frequency
- Handles ties intelligently with deterministic tie-breaking
- Operates independently per tenant

For detailed information about the algorithm, see
[WEIGHTED_ALGORITHM.md](WEIGHTED_ALGORITHM.md).

## Installation

The application uses PEP 723 script metadata, allowing uv to
automatically manage dependencies:

```bash
# Run the catcher script (processes all active tenants)
uv run catcher.py

# Run with options
uv run catcher.py --dry-run
uv run catcher.py --debug-weights
uv run catcher.py --force-notify
uv run catcher.py --tenant "Team"
```

For initial setup, run `setup.sh` to create the database schema and
a cronjob.

### Migrations

```bash
# Multi-tenant support
uv run migrate_to_tenants.py

# iCal sync support
uv run migrate_ical_support.py

# Remove auth columns (after UI removal)
uv run migrate_remove_auth.py
```

## Configuration

Create a `.env` file in the project directory (see `.env.example`):

```
DB_PATH=/path/to/user.db
HOLIDAY_API_URL=https://date.nager.at/Api/v3/IsTodayPublicHoliday/DE?countyCode=DE-BW
HOLIDAY_API_TIMEOUT=5
HOLIDAY_REGION=BW
SLACK_API_TIMEOUT=10
CLEANUP_RETENTION_DAYS=365
VACATION_RETENTION_DAYS=90
```

**Holiday Region Codes** (German states):
`BW`, `BY`, `BE`, `BB`, `HB`, `HH`, `HE`, `MV`, `NI`, `NW`, `RP`,
`SL`, `SN`, `ST`, `SH`, `TH`

## Database Schema

The application uses SQLite with the following tables:

- **user**: `id`, `mail`, `weekdays`, `last_chosen`, `tenant_id`,
  `display_name`
- **tenants**: `id`, `name`, `location`, `webhook_url`, `active`,
  `ical_url`, `created_at`
- **vacation**: `id`, `user_id`, `start_date`, `end_date`, `source`,
  `last_synced`, `ical_event_uid`
- **selection_history**: `id`, `user_id`, `selected_date`
- **vacation_sync_log**: `id`, `tenant_id`, `sync_timestamp`,
  `status`, `events_processed`, `users_matched`, `error_message`
