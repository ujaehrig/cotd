#!/usr/bin/env -S uv run --script

# /// script
# dependencies = []
# ///

import sqlite3
import argparse
import sys
import os
from pathlib import Path


def get_db_path(args):
    """Get database path from args or environment."""
    if args.db:
        return args.db
    return os.environ.get("DB_PATH", str(Path(__file__).parent / "user.db"))


def get_tenant_by_id_or_name(conn, identifier):
    """Get tenant by ID or name."""
    cursor = conn.execute(
        "SELECT id, name, location, webhook_url, active FROM tenants WHERE id = ? OR name = ?",
        (identifier if identifier.isdigit() else -1, identifier),
    )
    return cursor.fetchone()


def cmd_list(args):
    """List all tenants."""
    conn = sqlite3.connect(get_db_path(args))

    query = "SELECT id, name, location, webhook_url, active FROM tenants"
    if args.active_only:
        query += " WHERE active = 1"
    query += " ORDER BY id"

    cursor = conn.execute(query)
    tenants = cursor.fetchall()
    conn.close()

    if not tenants:
        print("No tenants found")
        return

    print(f"{'ID':<5} {'Name':<30} {'Location':<10} {'Webhook URL':<50} {'Active':<8}")
    print("-" * 103)
    for tenant in tenants:
        active_str = "Yes" if tenant[4] else "No"
        print(
            f"{tenant[0]:<5} {tenant[1]:<30} {tenant[2]:<10} {tenant[3]:<50} {active_str:<8}"
        )


def cmd_add(args):
    """Add a new tenant."""
    conn = sqlite3.connect(get_db_path(args))

    try:
        conn.execute(
            "INSERT INTO tenants (name, location, webhook_url) VALUES (?, ?, ?)",
            (args.name, args.location, args.webhook_url),
        )
        conn.commit()
        print(f"Tenant '{args.name}' added successfully")
    except sqlite3.IntegrityError:
        print("Error: Tenant name already exists", file=sys.stderr)
        conn.close()
        sys.exit(1)
    finally:
        conn.close()


def cmd_update(args):
    """Update an existing tenant."""
    conn = sqlite3.connect(get_db_path(args))

    tenant = get_tenant_by_id_or_name(conn, args.identifier)
    if not tenant:
        print(f"Error: Tenant '{args.identifier}' not found", file=sys.stderr)
        conn.close()
        sys.exit(1)

    tenant_id = tenant[0]
    updates = []
    params = []

    if args.name:
        updates.append("name = ?")
        params.append(args.name)
    if args.location:
        updates.append("location = ?")
        params.append(args.location)
    if args.webhook:
        updates.append("webhook_url = ?")
        params.append(args.webhook)

    if not updates:
        print("Error: No fields to update", file=sys.stderr)
        conn.close()
        sys.exit(1)

    params.append(tenant_id)
    query = f"UPDATE tenants SET {', '.join(updates)} WHERE id = ?"

    try:
        conn.execute(query, params)
        conn.commit()
        print("Tenant updated successfully")
    except sqlite3.IntegrityError:
        print("Error: Tenant name already exists", file=sys.stderr)
        conn.close()
        sys.exit(1)
    finally:
        conn.close()


def cmd_deactivate(args):
    """Deactivate a tenant."""
    conn = sqlite3.connect(get_db_path(args))

    tenant = get_tenant_by_id_or_name(conn, args.identifier)
    if not tenant:
        print(f"Error: Tenant '{args.identifier}' not found", file=sys.stderr)
        conn.close()
        sys.exit(1)

    conn.execute("UPDATE tenants SET active = 0 WHERE id = ?", (tenant[0],))
    conn.commit()
    conn.close()
    print(f"Tenant '{tenant[1]}' deactivated")


def cmd_activate(args):
    """Activate a tenant."""
    conn = sqlite3.connect(get_db_path(args))

    tenant = get_tenant_by_id_or_name(conn, args.identifier)
    if not tenant:
        print(f"Error: Tenant '{args.identifier}' not found", file=sys.stderr)
        conn.close()
        sys.exit(1)

    conn.execute("UPDATE tenants SET active = 1 WHERE id = ?", (tenant[0],))
    conn.commit()
    conn.close()
    print(f"Tenant '{tenant[1]}' activated")


def cmd_delete(args):
    """Delete a tenant."""
    conn = sqlite3.connect(get_db_path(args))

    tenant = get_tenant_by_id_or_name(conn, args.identifier)
    if not tenant:
        print(f"Error: Tenant '{args.identifier}' not found", file=sys.stderr)
        conn.close()
        sys.exit(1)

    # Check if tenant has users
    try:
        cursor = conn.execute(
            "SELECT COUNT(*) FROM user WHERE tenant_id = ?", (tenant[0],)
        )
        user_count = cursor.fetchone()[0]
    except sqlite3.OperationalError:
        # User table doesn't exist yet
        user_count = 0

    if user_count > 0 and not args.force:
        print(
            f"Error: Tenant has {user_count} users. Use --force to delete anyway",
            file=sys.stderr,
        )
        conn.close()
        sys.exit(1)

    conn.execute("DELETE FROM tenants WHERE id = ?", (tenant[0],))
    conn.commit()
    conn.close()
    print(f"Tenant '{tenant[1]}' deleted")


def main():
    parser = argparse.ArgumentParser(
        description="Manage tenants for Catcher of the Day"
    )
    parser.add_argument("--db", help="Database path (overrides DB_PATH env var)")

    subparsers = parser.add_subparsers(dest="command", required=True)

    # List command
    list_parser = subparsers.add_parser("list", help="List all tenants")
    list_parser.add_argument(
        "--active-only", action="store_true", help="Show only active tenants"
    )

    # Add command
    add_parser = subparsers.add_parser("add", help="Add a new tenant")
    add_parser.add_argument("name", help="Tenant name")
    add_parser.add_argument("location", help="Holiday region code (e.g., BW, BY, BE)")
    add_parser.add_argument("webhook_url", help="Slack webhook URL")

    # Update command
    update_parser = subparsers.add_parser("update", help="Update a tenant")
    update_parser.add_argument("identifier", help="Tenant ID or name")
    update_parser.add_argument("--name", help="New tenant name")
    update_parser.add_argument("--location", help="New location")
    update_parser.add_argument("--webhook", help="New webhook URL")

    # Deactivate command
    deactivate_parser = subparsers.add_parser("deactivate", help="Deactivate a tenant")
    deactivate_parser.add_argument("identifier", help="Tenant ID or name")

    # Activate command
    activate_parser = subparsers.add_parser("activate", help="Activate a tenant")
    activate_parser.add_argument("identifier", help="Tenant ID or name")

    # Delete command
    delete_parser = subparsers.add_parser("delete", help="Delete a tenant")
    delete_parser.add_argument("identifier", help="Tenant ID or name")
    delete_parser.add_argument(
        "--force", action="store_true", help="Force delete even if tenant has users"
    )

    args = parser.parse_args()

    # Route to command handlers
    if args.command == "list":
        cmd_list(args)
    elif args.command == "add":
        cmd_add(args)
    elif args.command == "update":
        cmd_update(args)
    elif args.command == "deactivate":
        cmd_deactivate(args)
    elif args.command == "activate":
        cmd_activate(args)
    elif args.command == "delete":
        cmd_delete(args)


if __name__ == "__main__":
    main()
