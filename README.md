# Catcher Of The Day

Simple script to trigger a workflow in Slack, which will show a catcher of the day.

You need to set up the workflow in Slack via the workflow builder. Choose a webhook as trigger. 

The script will call the triggering webhook and send an email address as parameter. The email address is chosen from the database using an advanced weighted selection algorithm that ensures fairness while avoiding consecutive day assignments when possible.

The script will also take vacation times and holidays into consideration. Old vacation entries are automatically cleaned up (default: 90 days retention).

## Multi-Tenant Support

The application supports multiple tenants (teams/departments), each with:
- Their own users and selection history
- Separate Slack webhook URLs for notifications
- Different holiday regions (German states)
- Independent catcher selection

### Running with Multiple Tenants

```bash
# Process all active tenants (default)
uv run catcher_weighted.py

# Process specific tenant
uv run catcher_weighted.py --tenant "Team Alpha"

# Dry run for specific tenant
uv run catcher_weighted.py --tenant "Team Alpha" --dry-run
```

### Managing Tenants

```bash
# List all tenants
uv run manage_tenants.py list

# Add a new tenant
uv run manage_tenants.py add "Team Beta" "BY" "https://hooks.slack.com/workflows/..."

# Update tenant
uv run manage_tenants.py update "Team Beta" --location "BW"

# Update tenant with iCal URL
uv run manage_tenants.py update "Team Beta" --ical-url "https://calendar.example.com/ical/team-beta.ics"

# Test iCal sync for a tenant
uv run manage_tenants.py test-sync "Team Beta"

# View sync status and logs
uv run manage_tenants.py sync-status "Team Beta"

# Deactivate/activate tenant
uv run manage_tenants.py deactivate "Team Beta"
uv run manage_tenants.py activate "Team Beta"
```

## Automatic Vacation Sync via iCal

The system supports automatic vacation synchronization from iCal/ICS calendar feeds. This eliminates the need for manual vacation entry.

### How It Works

1. Each tenant can have an iCal feed URL configured (e.g., from Google Calendar, Outlook, etc.)
2. Before each catcher selection, the system automatically fetches and parses the calendar
3. Vacation events are matched to users using fuzzy name matching
4. The vacation database is updated automatically
5. If the calendar is unreachable, cached vacation data is used as fallback

### Setting Up iCal Sync

1. **Get your calendar's iCal URL**:
   - Google Calendar: Settings → Calendar Settings → Integrate Calendar → Secret address in iCal format
   - Outlook: Calendar → Share → Publish → ICS link
   - Other calendars: Look for "Export" or "Subscribe" options

2. **Configure the tenant**:
   ```bash
   uv run manage_tenants.py update "Team Name" --ical-url "https://calendar.example.com/ical/feed.ics"
   ```

3. **Test the sync**:
   ```bash
   uv run manage_tenants.py test-sync "Team Name"
   ```

4. **Set display names for better matching** (optional but recommended):
   ```bash
   # List users
   uv run manage_users.py list
   
   # Set display name/nickname
   uv run manage_users.py set-display-name "john.doe@example.com" "Johnny"
   ```

### Calendar Event Format

The system extracts names from calendar event titles using fuzzy matching. Examples of supported formats:

- "Vacation - John Doe"
- "OOO: Jane Smith"
- "John - Urlaub"
- "Out of office Victoria"

The system automatically:
- Removes common vacation keywords (vacation, OOO, PTO, urlaub, etc.)
- Matches against user email addresses and display names
- Handles nicknames and variations (e.g., "Vicka" matches "Victoria")

### Configuration Options

Add these to your `.env` file:

```bash
# iCal sync timeout in seconds (default: 10)
ICAL_SYNC_TIMEOUT=10

# Fuzzy match threshold 0-100 (default: 80)
# Higher values require closer matches
FUZZY_MATCH_THRESHOLD=80

# Cache retention in hours (default: 24)
ICAL_CACHE_RETENTION_HOURS=24
```

### Managing Users

```bash
# List all users
uv run manage_users.py list

# List users for specific tenant
uv run manage_users.py list --tenant "Team Name"

# Show user details
uv run manage_users.py show "john.doe@example.com"

# Add a new user (tenant is required)
uv run manage_users.py add "john.doe@example.com" "Team Name"

# Add user with optional parameters
uv run manage_users.py add "john.doe@example.com" "Team Name" --weekdays "0,1,2,3,4" --display-name "Johnny"

# Update user details
uv run manage_users.py update "john.doe@example.com" --email "new@example.com"
uv run manage_users.py update "john.doe@example.com" --tenant "Team Beta"
uv run manage_users.py update "john.doe@example.com" --weekdays "0,1,2"

# Set or update display name for better iCal matching
uv run manage_users.py set-display-name "john.doe@example.com" "Johnny"

# Delete a user
uv run manage_users.py delete "john.doe@example.com"
```

**Note**: All user commands accept either email address or user ID as identifier.

### Migration to iCal Sync

If you're upgrading to use iCal sync:

```bash
# Run the migration script
uv run migrate_ical_support.py
```

This adds the necessary database columns for iCal support. Your existing manual vacation entries will remain in the database until you're ready to switch to automatic sync.

### Migrating to Multi-Tenant

If you're upgrading from a single-tenant installation:

```bash
# Run the migration script
uv run migrate_to_tenants.py
```

This creates a default tenant "Team Challengers" and assigns all existing users to it.

## Selection Algorithm

The system uses a sophisticated weighted selection algorithm that:
- Ensures fair distribution of duties over time
- Avoids consecutive day assignments when alternatives exist  
- Balances workload based on recent selection frequency
- Handles ties intelligently with deterministic tie-breaking
- Operates independently per tenant

For detailed information about the algorithm, see [WEIGHTED_ALGORITHM.md](WEIGHTED_ALGORITHM.md).

## Installation

### Option 1: Using uv with PEP 723 (Recommended)

The application now supports PEP 723 script metadata, allowing uv to automatically manage dependencies:

```bash
# Run the Flask web application
uv run app.py

# Test webhook functionality
uv run test_webhooks.py

# Run the catcher script (processes all active tenants)
uv run catcher_weighted.py

# Run with options
uv run catcher_weighted.py --dry-run          # Test without making changes
uv run catcher_weighted.py --debug-weights    # Show weight calculations
uv run catcher_weighted.py --force-notify     # Send notification even if catcher already selected
uv run catcher_weighted.py --tenant "Team"    # Process specific tenant
```

### Option 2: Traditional Installation

1. Run the script setup.sh. This will setup the database schema and a cronjob to run the catcher.py script every work-day at 7:30.
2. If you're upgrading from a previous version, run `python migrate_vacations.py` to update the database schema for multiple vacation periods.
3. For multi-tenant support, run `python migrate_to_tenants.py` to add tenant support.

## Configuration

Create a `.env` file in the project directory with the following variables:

```
# Database path (optional, defaults to user.db in the script directory)
DB_PATH=/path/to/user.db

# Holiday API settings (optional)
HOLIDAY_API_URL=https://date.nager.at/Api/v3/IsTodayPublicHoliday/DE?countyCode=DE-BW
HOLIDAY_API_TIMEOUT=5
HOLIDAY_REGION=BW  # German state code for fallback holiday detection (BW=Baden-Württemberg)

# Slack API timeout in seconds (optional)
SLACK_API_TIMEOUT=10

# Database cleanup settings (optional)
CLEANUP_RETENTION_DAYS=365  # Number of days to retain selection history
VACATION_RETENTION_DAYS=90  # Number of days to retain past vacation entries (default: 90)
```

**Holiday Region Codes**: The `HOLIDAY_REGION` setting uses German state codes for the fallback holiday library. Common codes include:
- `BW` - Baden-Württemberg (default)
- `BY` - Bayern (Bavaria)
- `BE` - Berlin
- `BB` - Brandenburg
- `HB` - Bremen
- `HH` - Hamburg
- `HE` - Hessen
- `MV` - Mecklenburg-Vorpommern
- `NI` - Niedersachsen
- `NW` - Nordrhein-Westfalen
- `RP` - Rheinland-Pfalz
- `SL` - Saarland
- `SN` - Sachsen
- `ST` - Sachsen-Anhalt
- `SH` - Schleswig-Holstein
- `TH` - Thüringen

## Managing Vacation Periods

The script now supports multiple vacation periods per user. You can manage vacation periods using the `manage_vacations.py` script:

### List all users
```
python manage_vacations.py list-users
```

### List all vacation periods
```
python manage_vacations.py list-vacations
```

### List vacation periods for a specific user
```
python manage_vacations.py list-vacations --user john@example.com
# or still works with user ID
python manage_vacations.py list-vacations --user 1
```

### Add a vacation period
```
python manage_vacations.py add <email_or_user_id> <start_date> [<end_date>]
```
Examples:
```
# Add a vacation period using email
python manage_vacations.py add john@example.com 2025-07-15 2025-07-30

# Add a single day vacation using email (end_date is optional)
python manage_vacations.py add john@example.com 2025-07-15

# Still works with user ID
python manage_vacations.py add 1 2025-07-15 2025-07-30
```

### Delete a vacation period
```
python manage_vacations.py delete <vacation_id>
```
Example:
```
python manage_vacations.py delete 5
```

## Database Schema

The application uses SQLite with the following schema:

### User Table
- `id`: Unique identifier for the user
- `mail`: Email address of the user
- `weekdays`: Days of the week the user is available (e.g., "0,1,2,3,4" for Monday-Friday)
- `last_chosen`: Date when the user was last selected as catcher

### Vacation Table
- `id`: Unique identifier for the vacation period
- `user_id`: Foreign key to the user table
- `start_date`: Start date of the vacation
- `end_date`: End date of the vacation
