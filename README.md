# Catcher Of The Day

Simple script to trigger a workflow in Slack, which will show a catcher of the day.

You need to set up the workflow in Slack via the workflow builder. Choose a webhook as trigger. 

The script will call the triggering webhook and send an email address as parameter. The email address is chosen from the database. The script chooses the address by a fairness strategy based on which address was not chosen for the longest time.

The script will also take vacation times and holidays into consideration. 

## Installation

1. Run the script setup.sh. This will setup the database schema and a cronjob to run the catcher.py script every work-day at 7:30.
2. If you're upgrading from a previous version, run `python migrate_vacations.py` to update the database schema for multiple vacation periods.

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

# Slack API timeout in seconds (optional)
SLACK_API_TIMEOUT=10
```

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
