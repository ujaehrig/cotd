#!/usr/bin/env -S uv run --script

# /// script
# dependencies = [
#    "python-dotenv>=1.0.0",
# ]
# ///

"""
User management script for Catcher of the Day.
Allows setting display names/nicknames for users.
"""

import sqlite3
import argparse
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


def get_db_path(args):
    """Get database path from args or environment."""
    if args.db:
        return args.db
    return os.environ.get("DB_PATH", str(Path(__file__).parent / "user.db"))


def get_user_by_id_or_email(conn, identifier):
    """Get user by ID or email."""
    cursor = conn.execute(
        "SELECT id, mail, display_name, tenant_id FROM user WHERE id = ? OR mail = ?",
        (identifier if identifier.isdigit() else -1, identifier),
    )
    return cursor.fetchone()


def cmd_list(args):
    """List all users."""
    conn = sqlite3.connect(get_db_path(args))

    query = """
        SELECT u.id, u.mail, u.display_name, t.name as tenant_name
        FROM user u
        LEFT JOIN tenants t ON u.tenant_id = t.id
    """
    
    if args.tenant:
        query += " WHERE t.name = ? OR t.id = ?"
        cursor = conn.execute(query, (args.tenant, args.tenant if args.tenant.isdigit() else -1))
    else:
        query += " ORDER BY u.id"
        cursor = conn.execute(query)

    users = cursor.fetchall()
    conn.close()

    if not users:
        print("No users found")
        return

    print(f"{'ID':<5} {'Email':<40} {'Display Name':<30} {'Tenant':<30}")
    print("-" * 105)
    for user in users:
        display_name = user[2] if user[2] else "(not set)"
        tenant_name = user[3] if user[3] else "(no tenant)"
        print(f"{user[0]:<5} {user[1]:<40} {display_name:<30} {tenant_name:<30}")


def cmd_set_display_name(args):
    """Set display name for a user."""
    conn = sqlite3.connect(get_db_path(args))

    user = get_user_by_id_or_email(conn, args.identifier)
    if not user:
        print(f"Error: User '{args.identifier}' not found", file=sys.stderr)
        conn.close()
        sys.exit(1)

    user_id, email = user[0], user[1]

    # Set display name (use None for empty string to clear)
    display_name = args.display_name if args.display_name else None

    conn.execute(
        "UPDATE user SET display_name = ? WHERE id = ?",
        (display_name, user_id)
    )
    conn.commit()
    conn.close()

    if display_name:
        print(f"Display name for '{email}' set to '{display_name}'")
    else:
        print(f"Display name for '{email}' cleared")


def cmd_show(args):
    """Show details for a specific user."""
    conn = sqlite3.connect(get_db_path(args))

    user = get_user_by_id_or_email(conn, args.identifier)
    if not user:
        print(f"Error: User '{args.identifier}' not found", file=sys.stderr)
        conn.close()
        sys.exit(1)

    user_id, email, display_name, tenant_id = user

    # Get tenant name
    cursor = conn.execute("SELECT name FROM tenants WHERE id = ?", (tenant_id,))
    tenant_row = cursor.fetchone()
    tenant_name = tenant_row[0] if tenant_row else "(no tenant)"

    conn.close()

    print(f"User ID: {user_id}")
    print(f"Email: {email}")
    print(f"Display Name: {display_name if display_name else '(not set)'}")
    print(f"Tenant: {tenant_name}")


def main():
    parser = argparse.ArgumentParser(
        description="Manage users for Catcher of the Day"
    )
    parser.add_argument("--db", help="Database path (overrides DB_PATH env var)")

    subparsers = parser.add_subparsers(dest="command", required=True)

    # List command
    list_parser = subparsers.add_parser("list", help="List all users")
    list_parser.add_argument("--tenant", help="Filter by tenant name or ID")

    # Show command
    show_parser = subparsers.add_parser("show", help="Show user details")
    show_parser.add_argument("identifier", help="User ID or email")

    # Set display name command
    set_name_parser = subparsers.add_parser("set-display-name", help="Set display name for a user")
    set_name_parser.add_argument("identifier", help="User ID or email")
    set_name_parser.add_argument("display_name", help="Display name/nickname (use empty string to clear)")

    args = parser.parse_args()

    # Route to command handlers
    if args.command == "list":
        cmd_list(args)
    elif args.command == "show":
        cmd_show(args)
    elif args.command == "set-display-name":
        cmd_set_display_name(args)


if __name__ == "__main__":
    main()
