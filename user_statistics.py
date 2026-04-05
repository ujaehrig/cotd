#!/usr/bin/env -S uv run --script

# /// script
# dependencies = []
# ///

import sqlite3
import os
from pathlib import Path

DATABASE_PATH = os.environ.get("DB_PATH", str(Path(__file__).parent / "user.db"))


def get_user_statistics():
    """Generate employment statistics from selection_history."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    query = """
        SELECT 
            u.mail,
            COUNT(sh.id) as total_selections,
            MAX(sh.selected_date) as last_selection
        FROM user u
        LEFT JOIN selection_history sh ON u.id = sh.user_id
        GROUP BY u.id, u.mail
        ORDER BY total_selections DESC
    """

    cursor.execute(query)
    results = cursor.fetchall()
    
    total_selections = sum(r[1] for r in results)
    
    conn.close()

    print(f"{'Email':<40} {'Selections':<12} {'%':<8} {'Last':<12}")
    print("=" * 77)

    for mail, selections, last in results:
        pct = f"{selections/total_selections*100:.1f}" if total_selections > 0 else "0.0"
        last_str = last if last else "N/A"
        print(f"{mail:<40} {selections:<12} {pct:<8} {last_str:<12}")


if __name__ == "__main__":
    get_user_statistics()
