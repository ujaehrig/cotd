#!/usr/bin/env -S uv run --script

# /// script
# dependencies = [
#    "python-dotenv>=1.0.0",
#    "icalendar>=7.0.0",
#    "rapidfuzz>=3.0.0",
#    "requests>=2.25.0",
# ]
# ///

import sqlite3
import argparse
import sys
import logging
from dotenv import load_dotenv
from db import DATABASE_PATH, get_db_connection

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


def get_db_path(args):
    """Get database path from args or default."""
    return args.db if args.db else DATABASE_PATH


def validate_url(url, field_name):
    """Validate that a URL uses https:// scheme."""
    if url and not url.startswith("https://"):
        print(f"Error: {field_name} must use https:// scheme", file=sys.stderr)
        sys.exit(1)


VALID_LOCATIONS = {
    "BW", "BY", "BE", "BB", "HB", "HH", "HE", "MV",
    "NI", "NW", "RP", "SL", "SN", "ST", "SH", "TH",
}


def validate_location(location):
    """Validate location is a known German state code."""
    if location not in VALID_LOCATIONS:
        print(f"Error: Invalid location '{location}'. Must be one of: {', '.join(sorted(VALID_LOCATIONS))}", file=sys.stderr)
        sys.exit(1)


def get_tenant_by_id_or_name(conn, identifier):
    """Get tenant by ID or name."""
    cursor = conn.execute(
        "SELECT id, name, location, webhook_url, active, ical_url FROM tenants WHERE id = ? OR name = ?",
        (identifier if identifier.isdigit() else -1, identifier),
    )
    return cursor.fetchone()


def cmd_list(args):
    """List all tenants."""
    conn = get_db_connection(get_db_path(args))

    query = "SELECT id, name, location, webhook_url, active, ical_url FROM tenants"
    if args.active_only:
        query += " WHERE active = 1"
    query += " ORDER BY id"

    cursor = conn.execute(query)
    tenants = cursor.fetchall()
    conn.close()

    if not tenants:
        print("No tenants found")
        return

    print(f"{'ID':<5} {'Name':<30} {'Location':<10} {'Active':<8} {'iCal URL':<50}")
    print("-" * 103)
    for tenant in tenants:
        active_str = "Yes" if tenant[4] else "No"
        ical_url = tenant[5] if tenant[5] else "(not set)"
        print(
            f"{tenant[0]:<5} {tenant[1]:<30} {tenant[2]:<10} {active_str:<8} {ical_url:<50}"
        )


def cmd_add(args):
    """Add a new tenant."""
    validate_url(args.webhook_url, "webhook_url")
    validate_location(args.location)
    conn = get_db_connection(get_db_path(args))

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
    conn = get_db_connection(get_db_path(args))

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
        validate_location(args.location)
        updates.append("location = ?")
        params.append(args.location)
    if args.webhook:
        validate_url(args.webhook, "webhook_url")
        updates.append("webhook_url = ?")
        params.append(args.webhook)
    if args.ical_url is not None:  # Allow empty string to clear
        if args.ical_url:
            validate_url(args.ical_url, "ical_url")
        updates.append("ical_url = ?")
        params.append(args.ical_url if args.ical_url else None)

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
    conn = get_db_connection(get_db_path(args))

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
    conn = get_db_connection(get_db_path(args))

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
    conn = get_db_connection(get_db_path(args))

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


def cmd_test_sync(args):
    """Test iCal sync for a tenant."""
    try:
        from vacation_sync import VacationSync
    except ImportError:
        print("Error: vacation_sync module not available", file=sys.stderr)
        sys.exit(1)

    conn = get_db_connection(get_db_path(args))
    tenant = get_tenant_by_id_or_name(conn, args.identifier)
    conn.close()

    if not tenant:
        print(f"Error: Tenant '{args.identifier}' not found", file=sys.stderr)
        sys.exit(1)

    tenant_id, tenant_name, location, webhook_url, active, ical_url = tenant

    if not ical_url:
        print(f"Error: Tenant '{tenant_name}' has no iCal URL configured", file=sys.stderr)
        sys.exit(1)

    print(f"Testing iCal sync for tenant '{tenant_name}'...")
    print(f"iCal URL: {ical_url}")
    print()

    sync = VacationSync()
    success, message = sync.sync_tenant_vacations(tenant_id, tenant_name, ical_url)

    if success:
        print(f"✓ Sync successful: {message}")
    else:
        print(f"✗ Sync failed: {message}", file=sys.stderr)
        sys.exit(1)


def cmd_sync_status(args):
    """Show sync status and logs for a tenant."""
    conn = get_db_connection(get_db_path(args))

    tenant = get_tenant_by_id_or_name(conn, args.identifier)
    if not tenant:
        print(f"Error: Tenant '{args.identifier}' not found", file=sys.stderr)
        conn.close()
        sys.exit(1)

    tenant_id, tenant_name = tenant[0], tenant[1]

    # Get recent sync logs
    cursor = conn.execute("""
        SELECT sync_timestamp, status, events_processed, users_matched, error_message
        FROM vacation_sync_log
        WHERE tenant_id = ?
        ORDER BY sync_timestamp DESC
        LIMIT ?
    """, (tenant_id, args.limit))

    logs = cursor.fetchall()
    conn.close()

    if not logs:
        print(f"No sync logs found for tenant '{tenant_name}'")
        return

    print(f"Sync logs for tenant '{tenant_name}':")
    print()
    print(f"{'Timestamp':<20} {'Status':<10} {'Events':<8} {'Matched':<8} {'Error':<50}")
    print("-" * 96)

    for log in logs:
        timestamp, status, events, matched, error = log
        error_str = error[:47] + "..." if error and len(error) > 50 else (error or "")
        print(f"{timestamp:<20} {status:<10} {events:<8} {matched:<8} {error_str:<50}")



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
    update_parser.add_argument("--ical-url", help="iCal feed URL (use empty string to clear)")

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

    # Test sync command
    test_sync_parser = subparsers.add_parser("test-sync", help="Test iCal sync for a tenant")
    test_sync_parser.add_argument("identifier", help="Tenant ID or name")

    # Sync status command
    sync_status_parser = subparsers.add_parser("sync-status", help="Show sync logs for a tenant")
    sync_status_parser.add_argument("identifier", help="Tenant ID or name")
    sync_status_parser.add_argument("--limit", type=int, default=10, help="Number of logs to show (default: 10)")

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
    elif args.command == "test-sync":
        cmd_test_sync(args)
    elif args.command == "sync-status":
        cmd_sync_status(args)


if __name__ == "__main__":
    main()
