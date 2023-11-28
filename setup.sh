#!/usr/bin/env bash

sqlite3 user.db < setup.sql

test -f setup-user.sql && sqlite3 user.db < setup-user.sql

ctab="30 7 * * 1-5	cd ${PWD} ; ./catcher.sh"
(crontab -u $(whoami) -l; echo "${ctab}" ) | crontab -u $(whoami) -
