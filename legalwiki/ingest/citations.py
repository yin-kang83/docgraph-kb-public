"""Extract law/article citations from judgments.basis into judgment_citations."""
from __future__ import annotations

import sqlite3

from .judgments_zip import parse_basis


def build_citations(conn: sqlite3.Connection, limit: int | None = None) -> dict:
    conn.execute("CREATE TABLE IF NOT EXISTS judgment_citations ("
                 "judgment_id TEXT NOT NULL, law TEXT, article TEXT, raw TEXT NOT NULL)")
    conn.execute("DELETE FROM judgment_citations")
    seen: set[tuple[str, str, str]] = set()
    rows, total = [], 0
    sql = "SELECT id,basis FROM judgments"
    if limit:
        sql += f" LIMIT {int(limit)}"
    for jid, basis in conn.execute(sql):
        for item in parse_basis(basis or ""):
            key = (jid, item.get("law") or "", item.get("article") or "")
            if key in seen:
                continue
            seen.add(key)
            rows.append((jid, item.get("law"), item.get("article"), item["raw"]))
            total += 1
        if len(rows) >= 5000:
            conn.executemany("INSERT INTO judgment_citations VALUES (?,?,?,?)", rows)
            conn.commit(); rows.clear()
    if rows:
        conn.executemany("INSERT INTO judgment_citations VALUES (?,?,?,?)", rows)
        conn.commit()
    return {"citations": total, "judgments": conn.execute("SELECT COUNT(DISTINCT judgment_id) FROM judgment_citations WHERE law IS NOT NULL").fetchone()[0]}
