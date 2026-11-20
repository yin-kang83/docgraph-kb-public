"""SQLite property graph store for legalwiki-kb (MVP)."""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schema.sql"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect(db: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    for table, cols in {
        "nodes": [("effective_from", "TEXT"), ("effective_to", "TEXT"), ("status", "TEXT")],
        "edges": [("as_of", "TEXT")],
    }.items():
        have = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
        for name, typ in cols:
            if name not in have:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {typ}")


def init_db(db: str | Path) -> sqlite3.Connection:
    conn = connect(db)
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    _migrate(conn)
    conn.commit()
    return conn


def add_node(
    conn, node_id: str, node_type: str, label: str = "", source_path: str | None = None,
    span_start: int | None = None, span_end: int | None = None,
    version: str | None = None, meta: dict | None = None,
    effective_from: str | None = None, effective_to: str | None = None,
    status: str | None = None,
) -> str:
    conn.execute(
        """INSERT OR REPLACE INTO nodes
           (id,type,label,source_path,span_start,span_end,version,hash,meta,
            effective_from,effective_to,status,created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (node_id, node_type, label, source_path, span_start, span_end, version, None,
         json.dumps(meta or {}, ensure_ascii=False), effective_from, effective_to, status, now()),
    )
    return node_id


def add_edge(conn, src: str, dst: str, edge_type: str, source_span: str | None = None,
             version: str | None = None, confidence: float | None = None,
             as_of: str | None = None) -> str:
    edge_id = f"E-{uuid.uuid4().hex[:12]}"
    conn.execute(
        """INSERT OR IGNORE INTO edges
           (id,src,dst,type,source_span,version,confidence,as_of,created_at)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (edge_id, src, dst, edge_type, source_span, version, confidence, as_of, now()),
    )
    return edge_id


def add_evidence(conn, evidence_id: str, claim_id: str, role: str, kind: str,
                 ref: str, span: str | None = None, valid: int = 1) -> str:
    conn.execute(
        """INSERT OR REPLACE INTO evidence
           (id,claim_id,role,kind,ref,span,valid,created_at)
           VALUES (?,?,?,?,?,?,?,?)""",
        (evidence_id, claim_id, role, kind, ref, span, valid, now()),
    )
    return evidence_id


def add_chunk(conn, chunk_id: str, node_id: str, text: str,
              span_start: int | None = None, span_end: int | None = None,
              version: str | None = None) -> str:
    conn.execute(
        """INSERT OR REPLACE INTO chunks
           (id,node_id,text,span_start,span_end,version,hash,token_count)
           VALUES (?,?,?,?,?,?,?,?)""",
        (chunk_id, node_id, text, span_start, span_end, version, None, len(text)),
    )
    conn.execute("DELETE FROM chunks_fts WHERE chunk_id = ?", (chunk_id,))
    conn.execute("INSERT INTO chunks_fts (chunk_id, text) VALUES (?, ?)", (chunk_id, text))
    return chunk_id
