# Catcher Of The Day

Simple script to trigger a workflow in Slack, which will show a catcher of the day.

You need to set up the workflow in Slack via the workflow builder. Choose a webhook as trigger. 

The script will call the triggering webhook and send an email address as parameter. The email address is chosen from the database using an advanced weighted selection algorithm that ensures fairness while avoiding consecutive day assignments when possible.

The script will also take vacation times and holidays into consideration.

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

# Deactivate/activate tenant
uv run manage_tenants.py deactivate "Team Beta"
uv run manage_tenants.py activate "Team Beta"
```

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
SLACK_WEBHOOK_URL=https://hooks.slack.com/workflows/...
```

Optional configuration variables:
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
