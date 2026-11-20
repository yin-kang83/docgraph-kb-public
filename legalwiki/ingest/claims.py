"""Rule-based candidate legal claim/evidence extraction (MVP).

This is candidate extraction, not legal interpretation.
"""
from __future__ import annotations

import hashlib
import re

from ..graph import store

SENT = re.compile(r"[^。；;\n]+[。；;]?")
CUES = re.compile(r"应当|不得|可以|必须|依照|违反|承担|无效|撤销|解除|管辖|适用|责任|处罚|赔偿")
DEONTIC = re.compile(r"应当|不得|可以|必须|依照")
LAW = re.compile(r"法|条例|规定|解释|法典|规章|law|legal", re.I)
CONTRACT = re.compile(r"合同|协议")
JUDGMENT = re.compile(r"判决|裁定|案")


def _id(prefix: str, *parts: str) -> str:
    h = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:10]
    return f"{prefix}-{h}"


def _kind(path: str) -> str:
    if CONTRACT.search(path):
        return "contract"
    if JUDGMENT.search(path):
        return "judgment"
    if LAW.search(path):
        return "law"
    return "document"


def extract_chunk(conn, chunk_id: str, text: str, source_path: str = "") -> int:
    path = source_path or ""
    kind = _kind(path)
    claims = 0
    for i, m in enumerate(SENT.finditer(text)):
        sent = m.group(0).strip()
        if len(sent) < 8 or not CUES.search(sent):
            continue
        claim_id = _id("CLM", chunk_id, str(i), sent)
        ev_id = _id("EVD", claim_id)
        norm = bool(DEONTIC.search(sent)) and kind in ("law", "regulation", "contract")
        role = "norm" if norm else "fact"
        store.add_node(conn, claim_id, "Claim", sent[:80], path)
        store.add_node(conn, ev_id, "Evidence", f"{chunk_id}#s{i}", path)
        store.add_evidence(conn, ev_id, claim_id, role, kind, f"{chunk_id}#s{i}", sent[:200], 1)
        store.add_edge(conn, claim_id, ev_id, "SUPPORTS", confidence=0.5)
        store.add_edge(conn, ev_id, chunk_id, "DERIVED_FROM", confidence=1.0)
        claims += 1
    return claims


def extract_all(conn) -> dict:
    rows = list(conn.execute(
        """SELECT c.id, c.text, n.source_path
           FROM chunks c LEFT JOIN nodes n ON n.id = c.node_id"""
    ))
    total = 0
    for r in rows:
        total += extract_chunk(conn, r["id"], r["text"], r["source_path"] or "")
    conn.commit()
    return {"chunks": len(rows), "claims": total}
