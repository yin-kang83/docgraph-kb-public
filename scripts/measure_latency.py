# -*- coding: utf-8 -*-
"""FTS 查询延迟实测。

用法：
    python scripts/measure_latency.py --db legal.db --query 合同纠纷 --query 交通事故
"""
from __future__ import annotations

import argparse
import sqlite3
import time


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--query", action="append", default=None)
    ap.add_argument("--table", default="judgments_fts")
    args = ap.parse_args()
    queries = args.query or ["合同纠纷", "交通事故", "民间借贷", "房屋租赁合同"]

    con = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True, timeout=30)
    cur = con.cursor()
    print(f"db={args.db} table={args.table} rows={cur.execute(f'select count(*) from {args.table}').fetchone()[0]}")
    total = 0.0
    for q in queries:
        t = time.perf_counter()
        n = cur.execute(f"select count(*) from {args.table} where {args.table} match ?",
                        (q,)).fetchone()[0]
        ms = (time.perf_counter() - t) * 1000
        total += ms
        print(f"  {q:12s} hits={n:10d}  {ms:8.1f} ms")
    print(f"total={total:.1f} ms  avg={total/len(queries):.1f} ms")
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
