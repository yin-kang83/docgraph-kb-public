"""Compact title table for fast title LIKE fallback."""
from __future__ import annotations

import sqlite3


def build_titles(conn: sqlite3.Connection) -> int:
    conn.execute("CREATE TABLE IF NOT EXISTS judgment_titles (id TEXT PRIMARY KEY, title TEXT NOT NULL)")
    conn.execute("PRAGMA synchronous=OFF")
    conn.execute("DELETE FROM judgment_titles")
    conn.execute("INSERT INTO judgment_titles (id,title) SELECT id,title FROM judgments")
    conn.commit()
    return conn.execute("SELECT COUNT(*) FROM judgment_titles").fetchone()[0]
