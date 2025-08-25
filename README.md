# Catcher Of The Day

Simple script to trigger a workflow in Slack, which will show a catcher of the day.

You need to set up the workflow in Slack via the workflow builder. Choose a webhook as trigger. 

The script will call the triggering webhook and send an email address as parameter. The email address is chosen from the database. The script chooses the address by a fairness strategy based on which address was not chosen for the longest time.

The script will also take vacation times and holidays into consideration. Holiday checking uses a fallback system: it first tries the configured web service API, and if that fails, it falls back to Python's `holidays` library for offline holiday detection. 

## Installation

Run the script setup.sh. This will setup the database schema and a cronjob to run the catcher.py script every work-day at 7:30.  

## Configuration

Add a file `config.ini` which contains a section `slack` with the entry `webhook_url`.

Example:
```ini
[slack]
webhook_url = https://hooks.slack.com/services/...
``` 

