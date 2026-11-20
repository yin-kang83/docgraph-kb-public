# -*- coding: utf-8 -*-
"""向量存取：judgment_embeddings BLOB + numpy 余弦 top-k。"""
from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime, timezone
from typing import Iterable, Sequence

import numpy as np

from .embedder import BaseEmbedder, text_for_judgment

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS judgment_embeddings (
  judgment_id TEXT NOT NULL,
  model TEXT NOT NULL,
  dim INTEGER NOT NULL,
  vector BLOB NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (judgment_id, model)
);
CREATE INDEX IF NOT EXISTS idx_judgment_embeddings_model
  ON judgment_embeddings(model);
CREATE TABLE IF NOT EXISTS embedding_runs (
  id TEXT PRIMARY KEY,
  model TEXT NOT NULL,
  dim INTEGER NOT NULL,
  backend TEXT NOT NULL,
  rows_embedded INTEGER NOT NULL,
  started_at TEXT NOT NULL,
  finished_at TEXT NOT NULL,
  status TEXT NOT NULL,
  detail TEXT
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_SQL)
    conn.commit()


def pack_vector(vector: np.ndarray | Sequence[float]) -> bytes:
    matrix = np.asarray(vector, dtype=np.float32).reshape(-1)
    return matrix.tobytes()


def unpack_vector(blob: bytes, dim: int) -> np.ndarray:
    if dim <= 0:
        raise ValueError("dim 必须 > 0")
    vector = np.frombuffer(blob, dtype=np.float32)
    if vector.size != dim:
        raise ValueError(f"向量维度不符：blob={vector.size} dim={dim}")
    return vector.copy()


def upsert_embedding(conn: sqlite3.Connection, judgment_id: str, model: str,
                     vector: np.ndarray | Sequence[float]) -> None:
    array = np.asarray(vector, dtype=np.float32).reshape(-1)
    dim = int(array.size)
    conn.execute(
        """INSERT INTO judgment_embeddings (judgment_id, model, dim, vector, created_at)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(judgment_id, model) DO UPDATE SET
             dim=excluded.dim, vector=excluded.vector, created_at=excluded.created_at""",
        (str(judgment_id), str(model), dim, pack_vector(array), _now()),
    )


def get_embedding(conn: sqlite3.Connection, judgment_id: str,
                  model: str) -> np.ndarray | None:
    row = conn.execute(
        "SELECT dim, vector FROM judgment_embeddings WHERE judgment_id=? AND model=?",
        (str(judgment_id), str(model)),
    ).fetchone()
    if row is None:
        return None
    return unpack_vector(row[1], int(row[0]))


def cosine_top_k(query: np.ndarray | Sequence[float], matrix: np.ndarray,
                 ids: Sequence[str], limit: int = 10) -> list[tuple[str, float]]:
    if limit <= 0 or len(ids) == 0:
        return []
    q = np.asarray(query, dtype=np.float32).reshape(-1)
    mat = np.asarray(matrix, dtype=np.float32)
    if mat.ndim != 2 or mat.shape[0] != len(ids):
        raise ValueError(f"matrix/ids 形状不符：{mat.shape} ids={len(ids)}")
    if mat.shape[1] != q.size:
        raise ValueError(f"query/matrix 维度不符：{q.size} vs {mat.shape[1]}")
    q_norm = float(np.linalg.norm(q))
    norms = np.linalg.norm(mat, axis=1)
    if q_norm == 0:
        return [(ids[i], 0.0) for i in range(min(limit, len(ids)))]
    scores = (mat @ q) / (norms * q_norm + 1e-12)
    order = np.argsort(-scores)[:limit]
    return [(str(ids[i]), float(scores[i])) for i in order]


def search_vectors(conn: sqlite3.Connection, query: np.ndarray | Sequence[float],
                   model: str, limit: int = 10) -> list[tuple[str, float]]:
    rows = conn.execute(
        "SELECT judgment_id, dim, vector FROM judgment_embeddings WHERE model=?",
        (str(model),),
    ).fetchall()
    if not rows:
        return []
    ids = [row[0] for row in rows]
    matrix = np.vstack([unpack_vector(row[2], int(row[1])) for row in rows]).astype(np.float32)
    return cosine_top_k(query, matrix, ids, limit)


def embed_judgments(conn: sqlite3.Connection, embedder: BaseEmbedder,
                    limit: int = 5000, model: str | None = None,
                    batch_size: int = 64, max_chars: int = 1000,
                    backend: str = "unknown") -> dict:
    """只嵌入尚未有该 model 向量的判例；默认 limit=5000（不碰全量）。"""
    ensure_schema(conn)
    model = model or embedder.name
    rows = conn.execute(
        """SELECT j.id, j.title, j.full_text
           FROM judgments j
           LEFT JOIN judgment_embeddings e
             ON e.judgment_id = j.id AND e.model = ?
           WHERE e.judgment_id IS NULL
           ORDER BY j.id
           LIMIT ?""",
        (model, int(limit)),
    ).fetchall()
    started = _now()
    embedded = 0
    dim = int(embedder.dim)
    for start in range(0, len(rows), max(1, batch_size)):
        batch = rows[start:start + max(1, batch_size)]
        texts = [text_for_judgment(row[1], row[2], max_chars=max_chars) for row in batch]
        matrix = np.asarray(embedder.embed(texts), dtype=np.float32)
        if matrix.ndim != 2 or matrix.shape[0] != len(batch):
            raise ValueError(f"embedder 返回维度异常：{matrix.shape}")
        dim = int(matrix.shape[1])
        for row, vector in zip(batch, matrix):
            upsert_embedding(conn, row[0], model, vector)
            embedded += 1
        conn.commit()
    finished = _now()
    run_id = hashlib.sha256(f"{model}:{started}:{embedded}".encode("utf-8")).hexdigest()[:16]
    conn.execute(
        """INSERT OR REPLACE INTO embedding_runs
           (id, model, dim, backend, rows_embedded, started_at, finished_at, status, detail)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (run_id, model, dim, backend, embedded, started, finished,
         "ok", f"limit={limit} max_chars={max_chars}"),
    )
    conn.commit()
    return {"model": model, "dim": dim, "backend": backend, "rows": embedded,
            "limit": int(limit), "started_at": started, "finished_at": finished}
