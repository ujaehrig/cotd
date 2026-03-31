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


def cmd_add(args):
    """Add a new user."""
    conn = sqlite3.connect(get_db_path(args))

    # Check if user already exists
    cursor = conn.execute("SELECT id FROM user WHERE mail = ?", (args.email,))
    if cursor.fetchone():
        print(f"Error: User with email '{args.email}' already exists", file=sys.stderr)
        conn.close()
        sys.exit(1)

    # Get tenant ID
    cursor = conn.execute(
        "SELECT id FROM tenants WHERE name = ? OR id = ?",
        (args.tenant, args.tenant if args.tenant.isdigit() else -1)
    )
    tenant_row = cursor.fetchone()
    if not tenant_row:
        print(f"Error: Tenant '{args.tenant}' not found", file=sys.stderr)
        conn.close()
        sys.exit(1)
    tenant_id = tenant_row[0]

    # Add user
    weekdays = args.weekdays if args.weekdays else "1,2,3,4,5"
    conn.execute(
        "INSERT INTO user (mail, weekdays, tenant_id, display_name) VALUES (?, ?, ?, ?)",
        (args.email, weekdays, tenant_id, args.display_name)
    )
    conn.commit()
    conn.close()

    print(f"User '{args.email}' added successfully")
    print(f"Assigned to tenant: {args.tenant}")
    if args.display_name:
        print(f"Display name: {args.display_name}")


def cmd_update(args):
    """Update user details."""
    conn = sqlite3.connect(get_db_path(args))

    user = get_user_by_id_or_email(conn, args.identifier)
    if not user:
        print(f"Error: User '{args.identifier}' not found", file=sys.stderr)
        conn.close()
        sys.exit(1)

    user_id, email = user[0], user[1]
    updates = []
    params = []

    if args.email:
        updates.append("mail = ?")
        params.append(args.email)

    if args.tenant:
        cursor = conn.execute(
            "SELECT id FROM tenants WHERE name = ? OR id = ?",
            (args.tenant, args.tenant if args.tenant.isdigit() else -1)
        )
        tenant_row = cursor.fetchone()
        if not tenant_row:
            print(f"Error: Tenant '{args.tenant}' not found", file=sys.stderr)
            conn.close()
            sys.exit(1)
        updates.append("tenant_id = ?")
        params.append(tenant_row[0])

    if args.weekdays:
        updates.append("weekdays = ?")
        params.append(args.weekdays)

    if not updates:
        print("Error: No updates specified", file=sys.stderr)
        conn.close()
        sys.exit(1)

    params.append(user_id)
    conn.execute(f"UPDATE user SET {', '.join(updates)} WHERE id = ?", params)
    conn.commit()
    conn.close()

    print(f"User '{email}' updated successfully")


def cmd_delete(args):
    """Delete a user."""
    conn = sqlite3.connect(get_db_path(args))

    user = get_user_by_id_or_email(conn, args.identifier)
    if not user:
        print(f"Error: User '{args.identifier}' not found", file=sys.stderr)
        conn.close()
        sys.exit(1)

    user_id, email = user[0], user[1]

    conn.execute("DELETE FROM user WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()

    print(f"User '{email}' deleted successfully")


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

    # Add command
    add_parser = subparsers.add_parser("add", help="Add a new user")
    add_parser.add_argument("email", help="User email address")
    add_parser.add_argument("tenant", help="Tenant name or ID")
    add_parser.add_argument("--weekdays", help="Available weekdays (default: 1,2,3,4,5 for Mon-Fri)")
    add_parser.add_argument("--display-name", help="Display name/nickname")

    # Update command
    update_parser = subparsers.add_parser("update", help="Update user details")
    update_parser.add_argument("identifier", help="User ID or email")
    update_parser.add_argument("--email", help="New email address")
    update_parser.add_argument("--tenant", help="New tenant name or ID")
    update_parser.add_argument("--weekdays", help="New available weekdays")

    # Delete command
    delete_parser = subparsers.add_parser("delete", help="Delete a user")
    delete_parser.add_argument("identifier", help="User ID or email")

    args = parser.parse_args()

    # Route to command handlers
    if args.command == "list":
        cmd_list(args)
    elif args.command == "show":
        cmd_show(args)
    elif args.command == "set-display-name":
        cmd_set_display_name(args)
    elif args.command == "add":
        cmd_add(args)
    elif args.command == "update":
        cmd_update(args)
    elif args.command == "delete":
        cmd_delete(args)


if __name__ == "__main__":
    main()
