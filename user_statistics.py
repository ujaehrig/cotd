#!/usr/bin/env -S uv run --script

# /// script
# dependencies = []
# ///

import argparse
from db import get_db_connection


def get_user_statistics(tenant_name=None):
    """Generate selection statistics from selection_history, grouped by tenant."""
    conn = get_db_connection()
    cursor = conn.cursor()

    if tenant_name:
        cursor.execute("""
            SELECT
                t.name as tenant_name,
                u.mail,
                COUNT(sh.id) as total_selections,
                MAX(sh.selected_date) as last_selection
            FROM user u
            LEFT JOIN selection_history sh ON u.id = sh.user_id
            LEFT JOIN tenants t ON u.tenant_id = t.id
            WHERE t.name = ?
            GROUP BY u.tenant_id, u.id, u.mail
            ORDER BY total_selections DESC
        """, (tenant_name,))
    else:
        cursor.execute("""
            SELECT
                t.name as tenant_name,
                u.mail,
                COUNT(sh.id) as total_selections,
                MAX(sh.selected_date) as last_selection
            FROM user u
            LEFT JOIN selection_history sh ON u.id = sh.user_id
            LEFT JOIN tenants t ON u.tenant_id = t.id
            GROUP BY u.tenant_id, u.id, u.mail
            ORDER BY t.name, total_selections DESC
        """)
    results = cursor.fetchall()
    conn.close()

    # Group by tenant and compute per-tenant totals
    tenants = {}
    for tenant_name, mail, selections, last in results:
        name = tenant_name or "(no tenant)"
        tenants.setdefault(name, []).append((mail, selections, last))

    for tenant_name, users in tenants.items():
        total = sum(s for _, s, _ in users)
        print(f"\n{tenant_name}")
        print(f"{'Email':<40} {'Selections':<12} {'%':<8} {'Last':<12}")
        print("-" * 77)
        for mail, selections, last in users:
            pct = f"{selections/total*100:.1f}" if total > 0 else "0.0"
            print(f"{mail:<40} {selections:<12} {pct:<8} {last or 'N/A':<12}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Show selection statistics")
    parser.add_argument("--tenant", help="Filter by tenant name")
    args = parser.parse_args()
    get_user_statistics(args.tenant)
