"""Bulk judgment index: metadata + full text FTS, no per-case graph.

Use when the corpus is too large for per-row Case/Court/Norm edges.
Graph/claim extraction remains for selected cases.
"""
from __future__ import annotations

import hashlib
import sqlite3
import time
from pathlib import Path

from .judgments_zip import _member_reader, clean_text, parse_date, parse_basis


def _id(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]


def build_fts(conn: sqlite3.Connection, full_text: bool = False) -> int:
    """重建 FTS 索引。

    full_text=False（默认）：只索引标题，体积小、建得快，全文检索降级 LIKE。
    full_text=True：标题+全文一起进 trigram 索引；体积约为标题版的 2.6 倍
    （实测：2014 语料 470 万条，31 GiB → 约 89 GiB，构建约 2–3 小时）。
    """
    conn.execute("PRAGMA synchronous=OFF")
    conn.execute("DELETE FROM judgments_fts")
    if full_text:
        conn.execute(
            "INSERT INTO judgments_fts (judgment_id,title,full_text) "
            "SELECT id,title,full_text FROM judgments")
    else:
        conn.execute(
            "INSERT INTO judgments_fts (judgment_id,title,full_text) "
            "SELECT id,title,'' FROM judgments")
    conn.commit()
    return conn.execute("SELECT COUNT(*) FROM judgments_fts").fetchone()[0]


def index_zip(conn: sqlite3.Connection, zip_path: str | Path,
              limit: int | None = None, dry_run: bool = False,
              build_fts_index: bool = True) -> dict:
    import zipfile

    zip_path = Path(zip_path)
    stats = {"files": 0, "rows": 0, "ok": 0, "reject": 0, "duplicates": 0,
             "started": time.time()}
    seen: set[str] = set()
    batch_j, batch_f = [], []
    conn.execute("PRAGMA synchronous=OFF")

    def flush():
        if dry_run:
            batch_j.clear(); batch_f.clear(); return
        if batch_j:
            conn.executemany(
                """INSERT OR IGNORE INTO judgments
                   (id,case_no,title,court,region,case_type,procedure,judgment_date,
                    cause,basis,full_text,text_hash,source_member,row_no)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", batch_j)
            conn.commit()
        batch_j.clear(); batch_f.clear()

    with zipfile.ZipFile(zip_path) as z:
        members = [n for n in z.namelist() if n.lower().endswith(".csv")]
        for member in members:
            stats["files"] += 1
            reader = _member_reader(z, member)
            for row_no, row in enumerate(reader, 1):
                if limit and stats["rows"] >= limit:
                    break
                stats["rows"] += 1
                case_no = (row.get("案号") or "").strip()
                title = clean_text(row.get("案件名称") or "")
                full = clean_text(row.get("全文") or "")
                if (not case_no and not title) or not full:
                    stats["reject"] += 1
                    continue
                h = hashlib.sha256(full.encode("utf-8")).hexdigest()
                if h in seen:
                    stats["duplicates"] += 1
                    continue
                seen.add(h)
                basis = "；".join(x["raw"] for x in parse_basis(row.get("法律依据") or ""))
                batch_j.append((
                    h[:32], case_no, title, clean_text(row.get("法院") or ""),
                    clean_text(row.get("所属地区") or ""), clean_text(row.get("案件类型") or ""),
                    clean_text(row.get("审理程序") or ""), parse_date(row.get("裁判日期") or ""),
                    clean_text(row.get("案由") or "")[:100], basis, full, h, member, row_no,
                ))
                batch_f.append((h[:32], title, full))
                stats["ok"] += 1
                if len(batch_j) >= 2000:
                    flush()
                    print(f"rows={stats['rows']} ok={stats['ok']} dup={stats['duplicates']}", flush=True)
            flush()
            if limit and stats["rows"] >= limit:
                break
    flush()
    if build_fts_index and not dry_run:
        stats["fts"] = build_fts(conn)
    stats["elapsed_sec"] = round(time.time() - stats["started"], 1)
    return stats
