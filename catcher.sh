#!/usr/bin/env bash

HD=$(dirname $(readlink  -f $0))
DB="${HD}/user.db"

. "${HD}/env.incl"

if [ ! -f "${DB}" ] ; then
	echo "DB not found: ${DB}"
	exit 1
fi

STATUSCODE=$(curl --silent --output /dev/stderr --write-out "%{http_code}" https://date.nager.at/Api/v2/IsTodayPublicHoliday/DE)
if [ $STATUSCODE -eq 200 ]  ; then
	echo "Public holiday"
	exit 2
fi

TF=$(tempfile)
cat > "${TF}" <<-EOF
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
EOF

MAIL="$(sqlite3 -init /dev/null -noheader "${DB}" < "${TF}" 2> /dev/null)"
rm "${TF}"

DATA='{ "uid": "'"${MAIL}"'" }'

curl -s -X POST \
	--data "${DATA}" \
	-H "Content-Type: application/json" \
	"${SLACK_WEBHOOK}"


