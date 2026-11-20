# -*- coding: utf-8 -*-
"""全文 FTS 构建成本实测：从现有库抽样 N 条到临时库，建「标题+全文」trigram 索引。

复刻 build_judgments_fts(full_text=True) 的条件：synchronous=OFF、WAL、分批 commit。
输出：构建耗时、体积、每行成本、按行数外推值。

用法：
    python scripts/measure_fts_build.py --db legal.db --limit 50000
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
import tempfile
import time


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True, help="源库（只读）")
    ap.add_argument("--limit", type=int, default=50_000)
    ap.add_argument("--batch", type=int, default=50_000)
    ap.add_argument("--total-rows", type=int, default=0,
                    help="源库总行数，用于外推（默认自动 count）")
    args = ap.parse_args()

    tmp = os.path.join(tempfile.gettempdir(), "fts_probe.db")
    for suf in ("", "-wal", "-shm"):
        if os.path.exists(tmp + suf):
            os.remove(tmp + suf)

    con = sqlite3.connect(tmp)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=OFF")
    con.execute("PRAGMA cache_size=-131072")
    con.execute("""CREATE TABLE judgments (
        id TEXT PRIMARY KEY, case_no TEXT, title TEXT, court TEXT, region TEXT,
        case_type TEXT, procedure TEXT, judgment_date TEXT, cause TEXT,
        basis TEXT, full_text TEXT, text_hash TEXT, source_member TEXT, row_no INTEGER)""")
    con.execute("""CREATE VIRTUAL TABLE judgments_fts USING fts5(
        judgment_id UNINDEXED, title, full_text, tokenize='trigram')""")
    con.commit()

    src = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True, timeout=30)
    total = args.total_rows or src.execute("select count(*) from judgments").fetchone()[0]
    con.execute("ATTACH DATABASE ? AS s", (args.db,))
    t = time.perf_counter()
    con.execute("INSERT INTO judgments SELECT * FROM s.judgments LIMIT ?", (args.limit,))
    con.commit()
    con.execute("DETACH DATABASE s")
    copy_s = time.perf_counter() - t
    n = con.execute("select count(*) from judgments").fetchone()[0]
    print(f"copied={n} rows in {copy_s:.1f}s")

    t = time.perf_counter()
    lo = 1
    while lo <= n:
        hi = min(lo + args.batch - 1, n)
        con.execute("INSERT INTO judgments_fts (judgment_id,title,full_text) "
                    "SELECT id,title,full_text FROM judgments WHERE rowid BETWEEN ? AND ?",
                    (lo, hi))
        con.commit()
        lo = hi + 1
    build_s = time.perf_counter() - t
    con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    con.commit()
    size_gb = os.path.getsize(tmp) / 1024**3 * 1024  # MB-ish guard
    db_mb = os.path.getsize(tmp) / 1024**2
    con.close()
    src.close()

    print(f"fulltext_fts_build_sec={build_s:.1f}")
    print(f"per_row_ms={build_s*1000/n:.2f}")
    print(f"db_mb={db_mb:.1f}  bytes_per_row={os.path.getsize(tmp)/n:.0f}")
    print(f"extrapolate_{total}_hours={build_s/n*total/3600:.2f}")
    print(f"extrapolate_{total}_GB={os.path.getsize(tmp)/n*total/1024**3:.1f}")
    print(f"tmp_db={tmp}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
