#!/usr/bin/env -S uv run --script

# /// script
# dependencies = [
#    "flask>=3.0.0",
#    "python-dotenv>=1.0.0",
# ]
# ///

"""Small web app that handles catcher takeover registrations."""

import datetime
import hashlib
import hmac
import logging
import sqlite3

from flask import Flask, request
from dotenv import load_dotenv

from db import DATABASE_PATH

load_dotenv()

app = Flask(__name__)

# Ensure takeover_log table exists
_conn = sqlite3.connect(DATABASE_PATH)
_conn.execute(
    "CREATE TABLE IF NOT EXISTS takeover_log "
    "(id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id INTEGER NOT NULL, "
    "takeover_date DATE NOT NULL, new_user_id INTEGER NOT NULL)"
)
_conn.commit()
_conn.close()
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

THANK_YOU_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>Takeover registered</title>
<style>body{font-family:sans-serif;display:flex;justify-content:center;
align-items:center;height:100vh;margin:0;background:#f5f5f5}
.card{background:#fff;padding:2rem;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,.1);
text-align:center;max-width:400px}</style></head>
<body><div class="card"><h1>&#10004; Thank you!</h1>
<p>You are now registered as today's catcher.</p></div></body></html>
"""

ERROR_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>Error</title>
<style>body{{font-family:sans-serif;display:flex;justify-content:center;
align-items:center;height:100vh;margin:0;background:#f5f5f5}}
.card{{background:#fff;padding:2rem;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,.1);
text-align:center;max-width:400px;color:#c00}}</style></head>
<body><div class="card"><h1>&#10060; Error</h1><p>{message}</p></div></body></html>
"""


def _verify_nonce(tenant_id: str, nonce: str, secret: str) -> bool:
    today = datetime.date.today().isoformat()
    expected = hmac.new(
        secret.encode(), f"{tenant_id}{today}".encode(), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(nonce, expected)


@app.route("/takeover")
def takeover():
    tenant_id = request.args.get("tenant", "")
    nonce = request.args.get("nonce", "")
    uid = request.args.get("uid", "").lstrip("@")

    if not tenant_id or not nonce or not uid:
        return ERROR_HTML.format(message="Missing parameters."), 400

    conn = sqlite3.connect(DATABASE_PATH)
    try:
        row = conn.execute(
            "SELECT takeover_secret FROM tenants WHERE id = ? AND active = 1",
            (tenant_id,),
        ).fetchone()
        if not row or not row[0]:
            return ERROR_HTML.format(message="Invalid tenant."), 403

        if not _verify_nonce(tenant_id, nonce, row[0]):
            return ERROR_HTML.format(message="Link expired or invalid."), 403

        # Find the new catcher user (uid may be a Slack username, not email)
        uid_escaped = uid.replace("%", "\\%").replace("_", "\\_")
        user = conn.execute(
            "SELECT id FROM user WHERE (mail = ? OR mail LIKE ? ESCAPE '\\' OR display_name = ?) AND tenant_id = ?",
            (uid, uid_escaped + "@%", uid, tenant_id),
        ).fetchone()
        if not user:
            return ERROR_HTML.format(message="User not found."), 404

        today = datetime.date.today().isoformat()

        # Check if a takeover already happened today for this tenant
        existing = conn.execute(
            "SELECT user_id FROM selection_history WHERE selected_date = ? AND user_id IN "
            "(SELECT id FROM user WHERE tenant_id = ?)",
            (today, tenant_id),
        ).fetchone()
        if existing and existing[0] == user[0]:
            return THANK_YOU_HTML  # Idempotent: same user clicking again

        takeover_count = conn.execute(
            "SELECT COUNT(*) FROM takeover_log WHERE tenant_id = ? AND takeover_date = ?",
            (tenant_id, today),
        ).fetchone()[0]
        if takeover_count > 0:
            return ERROR_HTML.format(
                message="A takeover has already been registered today."
            ), 409

        # Find the previous catcher and reset their last_chosen
        prev = conn.execute(
            "SELECT user_id FROM selection_history WHERE selected_date = ? AND user_id IN "
            "(SELECT id FROM user WHERE tenant_id = ?)",
            (today, tenant_id),
        ).fetchone()
        if prev:
            prior = conn.execute(
                "SELECT selected_date FROM selection_history "
                "WHERE user_id = ? AND selected_date < ? ORDER BY selected_date DESC LIMIT 1",
                (prev[0], today),
            ).fetchone()
            conn.execute(
                "UPDATE user SET last_chosen = ? WHERE id = ?",
                (prior[0] if prior else None, prev[0]),
            )

        # Replace today's selection_history entry
        conn.execute(
            "DELETE FROM selection_history WHERE selected_date = ? AND user_id IN "
            "(SELECT id FROM user WHERE tenant_id = ?)",
            (today, tenant_id),
        )
        conn.execute(
            "INSERT INTO selection_history (user_id, selected_date) VALUES (?, ?)",
            (user[0], today),
        )
        conn.execute("UPDATE user SET last_chosen = ? WHERE id = ?", (today, user[0]))
        conn.execute(
            "INSERT INTO takeover_log (tenant_id, takeover_date, new_user_id) VALUES (?, ?, ?)",
            (tenant_id, today, user[0]),
        )
        conn.commit()

        logging.info(f"Takeover: tenant={tenant_id} new_catcher={uid}")
        return THANK_YOU_HTML
    finally:
        conn.close()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8090)
