#/usr/bin/env python

import configparser
import json
import requests

config = configparser.ConfigParser()
config.read('catcher.ini')


def isHoliday():
    response = requests.get('https://date.nager.at/Api/v2/IsTodayPublicHoliday/DE')
    return response.status_code == 200


def main():
    if isHoliday:
        return


    conn = sqlite3.connect("users.db")
    cur = conn.cursor()

    cur.execute("""
    	create temp table x(mail text);
        insert into x 
            select mail 
            from user 
            where weekdays like strftime('%%%w%%','now')
            and ((vacation_start is null or vacation_end is null) 
                or (date() < vacation_start or date() > vacation_end))
            order by last_chosen asc
            limit 1;
        update user set last_chosen = date() where mail = (select mail from x);
        select mail from x;
    """)

    mail = cur.fetchone()
    if mail is None:
        return

    data = { 'uid': mail }
    headers = {'Content-type': 'application/json' }
    response = requests.post(config.get('slack', 'webhook')), headers=headers, data = data)


if __name__ == "__main__":
    main()
