# -*- coding: utf-8 -*-
"""Hybrid 检索：FTS 召回 + 向量召回 + RRF/加权融合。"""
from __future__ import annotations

import sqlite3
from typing import Mapping, Sequence

from .embedder import BaseEmbedder
from .vector_store import search_vectors


def fts_search(conn: sqlite3.Connection, query: str, limit: int = 50) -> list[dict]:
    """FTS5 trigram 召回；查询过短/不支持时降级 LIKE。返回按 rank 排序的 id。"""
    query = str(query or "").strip()
    if not query or limit <= 0:
        return []
    rows = []
    try:
        rows = conn.execute(
            """SELECT judgment_id, bm25(judgments_fts) AS rank
               FROM judgments_fts
               WHERE judgments_fts MATCH ?
               ORDER BY rank
               LIMIT ?""",
            (query, int(limit)),
        ).fetchall()
    except sqlite3.OperationalError:
        rows = []
    if not rows:
        like = f"%{query}%"
        try:
            try:
                rows = conn.execute(
                    """SELECT id, 0.0 FROM judgment_titles
                       WHERE title LIKE ?
                       ORDER BY id LIMIT ?""",
                    (like, int(limit)),
                ).fetchall()
            except sqlite3.OperationalError:
                rows = conn.execute(
                    """SELECT id, 0.0 FROM judgments
                       WHERE title LIKE ?
                       ORDER BY id LIMIT ?""",
                    (like, int(limit)),
                ).fetchall()
            if not rows:
                rows = conn.execute(
                    """SELECT id, 0.0 FROM judgments
                       WHERE full_text LIKE ?
                       ORDER BY id LIMIT ?""",
                    (like, int(limit)),
                ).fetchall()
        except sqlite3.OperationalError:
            return []
    return [{"judgment_id": row[0], "rank": index + 1, "fts_score": row[1]}
            for index, row in enumerate(rows)]


def vector_search(conn: sqlite3.Connection, query: str, embedder: BaseEmbedder,
                  model: str | None = None, limit: int = 50) -> list[dict]:
    query = str(query or "").strip()
    if not query or limit <= 0:
        return []
    vector = embedder.embed([query])[0]
    hits = search_vectors(conn, vector, model or embedder.name, limit)
    return [{"judgment_id": jid, "rank": index + 1, "vector_score": score}
            for index, (jid, score) in enumerate(hits)]


def rrf_fuse(rankings: Mapping[str, Sequence[str]], k: int = 60,
             weights: Mapping[str, float] | None = None) -> list[tuple[str, float]]:
    """Reciprocal Rank Fusion：score = Σ w_s/(k+rank_s)。"""
    weights = dict(weights or {})
    scores: dict[str, float] = {}
    for source, ids in rankings.items():
        weight = float(weights.get(source, 1.0))
        for rank, judgment_id in enumerate(ids, start=1):
            scores[judgment_id] = scores.get(judgment_id, 0.0) + weight / (k + rank)
    return sorted(scores.items(), key=lambda item: (-item[1], item[0]))


def weighted_fuse(rankings: Mapping[str, Sequence[str]],
                  weights: Mapping[str, float] | None = None) -> list[tuple[str, float]]:
    """简化的加权 rank 融合（无 k）；用于需要拉开权重的场景。"""
    weights = dict(weights or {})
    scores: dict[str, float] = {}
    for source, ids in rankings.items():
        weight = float(weights.get(source, 1.0))
        for rank, judgment_id in enumerate(ids, start=1):
            scores[judgment_id] = scores.get(judgment_id, 0.0) + weight / rank
    return sorted(scores.items(), key=lambda item: (-item[1], item[0]))


def search_hybrid(conn: sqlite3.Connection, query: str, embedder: BaseEmbedder | None,
                  limit: int = 10, model: str | None = None,
                  fts_limit: int = 50, vector_limit: int = 50,
                  weights: Mapping[str, float] | None = None,
                  mode: str = "rrf") -> list[dict]:
    """FTS + 向量混合；缺向量/空库自动降级，不伪造结果。"""
    fts_hits = fts_search(conn, query, fts_limit)
    vector_hits = []
    if embedder is not None:
        try:
            vector_hits = vector_search(conn, query, embedder, model, vector_limit)
        except Exception:  # noqa: BLE001 - 向量不可用时降级 FTS，而不是整体失败
            vector_hits = []
    rankings = {
        "fts": [hit["judgment_id"] for hit in fts_hits],
        "vector": [hit["judgment_id"] for hit in vector_hits],
    }
    fused = rrf_fuse(rankings, weights=weights) if mode == "rrf" else weighted_fuse(rankings, weights)
    fused = fused[:max(0, int(limit))]
    if not fused:
        return []
    ids = [judgment_id for judgment_id, _ in fused]
    placeholders = ",".join("?" for _ in ids)
    titles = {row[0]: row[1] for row in conn.execute(
        f"SELECT id, title FROM judgments WHERE id IN ({placeholders})", ids)}
    sources = {
        judgment_id: [source for source, hit_ids in rankings.items() if judgment_id in hit_ids]
        for judgment_id in ids
    }
    return [{"judgment_id": judgment_id, "title": titles.get(judgment_id, ""),
             "score": score, "sources": sources[judgment_id]} for judgment_id, score in fused]
