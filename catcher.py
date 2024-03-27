#!/usr/bin/env python

import configparser
import json
import requests
import sqlite3
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

config = configparser.ConfigParser()
config.read('config.ini')


def is_holiday():
    """
    Checks if today is a public holiday in Germany.

    :return: True if today is a public holiday, False otherwise
    """
    try:
        response = requests.get('https://date.nager.at/Api/v2/IsTodayPublicHoliday/DE', timeout=1)
        if response.status_code == 200:
            logging.info('Holiday detected')
        return response.status_code == 200
    except requests.exceptions.RequestException as e:
        logging.error('Failed to check holiday status: %s', e)
        return False


def trigger_slack(mail):
    """
    :param mail: The email address of the user to be notified on Slack.
    :type mail: str
    :return: None
    :rtype: None

    This method triggers a Slack notification for the specified user using their email address. It sends a POST request to the configured Slack webhook with the email address as the payload.

    Example usage:

    ```
    trigger_slack('user@example.com')
    ```

    Note: This method requires the `config` object to be properly configured with the Slack webhook URL.
    """
    try:
        data = {'uid': mail}
        headers = {'Content-type': 'application/json'}
        response = requests.post(config.get('slack', 'webhook'), headers=headers, data=json.dumps(data), timeout=1)
        if response.status_code == 200:
            logging.info("Chosen Catcher: %s", mail)
        else:
            logging.warn("Webhook returned: %d (%s)", response.status_code, response.json)
    except requests.exceptions.RequestException as e:
        logging.error('Failed to trigger Slack notification: %s', e)

def find_next_catcher():
    """
    This method `find_next_catcher` is used to retrieve the email address
    of the next user who is available.
    The method retrieves the email address from a database table based
    on specific conditions.

    :return: The email address of the next available user or None
    """
    conn = sqlite3.connect("user.db")
    cur = conn.cursor()

    cur.execute("""
        select mail 
          from user
         where last_chosen = date()
    """)

    result = cur.fetchone()
    if result is None:
        cur.execute("""
            select mail 
                from user 
            where weekdays like strftime('%%%w%%','now')
                and ((vacation_start is null or vacation_end is null) 
                    or (date() < vacation_start or date() > vacation_end))
            order by last_chosen asc
            limit 1
        """)

        result = cur.fetchone()
        if result is not None:
            cur.execute("update user set last_chosen = date() where mail = ?", result)
            conn.commit()

    conn.close()
    return None if result is None else result[0]


def main():
    if is_holiday():
        return

    mail = find_next_catcher()
    trigger_slack(mail)


if __name__ == "__main__":
    main()
