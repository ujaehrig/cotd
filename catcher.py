#!/usr/bin/env python

import configparser
import json
import requests
import sqlite3

config = configparser.ConfigParser()
config.read('config.ini')


def is_holiday():
    try:
        response = requests.get('https://date.nager.at/Api/v2/IsTodayPublicHoliday/DE')
        return response.status_code == 200
    except:
        return False


def main():
    if is_holiday():
        return

    conn = sqlite3.connect("user.db")
    cur = conn.cursor()

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
    if result is None:
        return

    mail = result[0]
    cur.execute("""
         update user set last_chosen = date() where mail = ?
    """, result)
    conn.commit()

    data = {'uid': mail}
    headers = {'Content-type': 'application/json'}
    response = requests.post(config.get('slack', 'webhook'), headers=headers, data=json.dumps(data))

    conn.close()

if __name__ == "__main__":
    main()
