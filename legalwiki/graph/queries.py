"""Queries for the legal graph."""
from __future__ import annotations


def search_chunks(conn, query: str, limit: int = 5):
    return list(conn.execute(
        """SELECT chunk_id, text, bm25(chunks_fts) AS rank
           FROM chunks_fts WHERE chunks_fts MATCH ?
           ORDER BY rank LIMIT ?""",
        (query, limit),
    ))


def evidence_chain(conn, claim_id: str):
    return list(conn.execute(
        """SELECT e.id, e.role, e.kind, e.ref, e.span, e.valid
           FROM evidence e
           JOIN edges ed ON ed.dst = e.id AND ed.type = 'SUPPORTS'
           WHERE ed.src = ? ORDER BY e.id""",
        (claim_id,),
    ))


def articles_of(conn, law_id: str):
    return list(conn.execute(
        """WITH RECURSIVE sub(id,type) AS (
             SELECT id,type FROM nodes WHERE id=?
             UNION
             SELECT n.id,n.type FROM edges e JOIN sub s ON e.src=s.id
             JOIN nodes n ON n.id=e.dst
             WHERE e.type='CONTAINS'
           )
           SELECT id,type FROM sub WHERE type='Article'""",
        (law_id,),
    ))


def citations_of(conn, norm_id: str):
    return list(conn.execute(
        """SELECT ed.src, n.label FROM edges ed JOIN nodes n ON n.id=ed.src
           WHERE ed.dst=? AND ed.type='CITES'""",
        (norm_id,),
    ))
