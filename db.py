"""Shared database configuration and connection helper."""

import os
import sqlite3
from pathlib import Path

DATABASE_PATH = os.environ.get("DB_PATH", str(Path(__file__).parent / "user.db"))


def get_db_connection(db_path: str | None = None) -> sqlite3.Connection:
    """
    Create and return a database connection with Row factory.

    Args:
        db_path: Optional path override. Defaults to DATABASE_PATH.

    Returns:
        sqlite3.Connection with row_factory set to sqlite3.Row
    """
    path = db_path or DATABASE_PATH
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.row_factory = sqlite3.Row
    return conn
