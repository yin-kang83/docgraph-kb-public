"""Judgment CSV ingest: Case -> Court, Case -> Norm (CITES), full-text chunks.

Expected columns (header names):
  案号, 案件名称, 法院, 所属地区, 案件类型, 审理程序, 裁判日期, 案由, 法律依据, 全文
"""
from __future__ import annotations

import csv
import hashlib
import re
from pathlib import Path

from ..graph import store


def _id(prefix: str, *parts: str) -> str:
    h = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:10]
    return f"{prefix}-{h}"


def _chunks(text: str, max_chars: int = 800) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    out, buf = [], ""
    for i in range(0, len(text), max_chars):
        out.append(text[i:i + max_chars])
    return out


def ingest_csv(conn, path: str | Path) -> dict:
    path = Path(path)
    cases = chunks = norms = 0
    with path.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            case_no = (row.get("案号") or "").strip()
            title = (row.get("案件名称") or "").strip()
            if not case_no and not title:
                continue
            cid = _id("CASE", case_no or title, path.name)
            court = (row.get("法院") or "").strip()
            meta = {
                "court": court,
                "region": (row.get("所属地区") or "").strip(),
                "case_type": (row.get("案件类型") or "").strip(),
                "procedure": (row.get("审理程序") or "").strip(),
                "judgment_date": (row.get("裁判日期") or "").strip(),
                "cause": (row.get("案由") or "").strip(),
            }
            store.add_node(conn, cid, "Case", title or case_no, str(path), meta=meta)
            cases += 1

            if court:
                court_id = _id("COURT", court)
                store.add_node(conn, court_id, "Court", court, meta={"region": meta["region"]})
                store.add_edge(conn, cid, court_id, "HEARD_BY")

            full = (row.get("全文") or "").strip()
            for i, piece in enumerate(_chunks(full)):
                ch_id = _id("CH", cid, str(i))
                store.add_chunk(conn, ch_id, cid, piece)
                store.add_edge(conn, cid, ch_id, "CONTAINS")
                chunks += 1

            basis = (row.get("法律依据") or "").strip()
            if basis:
                for norm in re.split(r"[；;]\s*", basis):
                    norm = norm.strip()
                    if not norm:
                        continue
                    nid = _id("NORM", norm)
                    store.add_node(conn, nid, "Norm", norm[:120], str(path))
                    store.add_edge(conn, cid, nid, "CITES")
                    norms += 1
    conn.commit()
    return {"file": str(path), "cases": cases, "chunks": chunks, "norms": norms}


def ingest_dir(conn, root: str | Path, pattern: str = "*.csv") -> list[dict]:
    root = Path(root)
    files = [root] if root.is_file() else sorted(root.rglob(pattern))
    return [ingest_csv(conn, p) for p in files]
