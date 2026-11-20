# -*- coding: utf-8 -*-
"""通用数据库验收：行数一致性 / FTS 行为 / 抽样完整性 / 可选 quick_check。

用法：
    python scripts/verify_db.py --db path/to/legal.db
    python scripts/verify_db.py --db legal.db --quick-check
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
import time

TABLES = ("judgments", "judgments_fts", "judgment_titles", "judgment_citations")


def count(cur, table: str) -> int | None:
    try:
        return cur.execute(f"select count(*) from {table}").fetchone()[0]
    except sqlite3.Error:
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--quick-check", action="store_true", help="全库页扫描（大库很慢）")
    ap.add_argument("--expect-judgments", type=int, default=None)
    args = ap.parse_args()

    con = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True, timeout=30)
    cur = con.cursor()
    ok = True

    print("== 行数 ==")
    n_j = count(cur, "judgments")
    counts = {t: count(cur, t) for t in TABLES}
    for t, n in counts.items():
        print(f"  {t:24s} = {n}")
    if n_j is None:
        print("缺少 judgments 表"); return 2
    if args.expect_judgments is not None:
        same = n_j == args.expect_judgments
        print(f"  judgments == 期望 {args.expect_judgments}: {'PASS' if same else 'FAIL'}")
        ok &= same
    for t in ("judgments_fts", "judgment_titles"):
        if counts.get(t) is not None and counts[t] != n_j:
            print(f"  FAIL {t} != judgments"); ok = False

    print("== FTS 行为（trigram 需 >=3 字符）==")
    for q in ("合同纠纷", "合同"):
        try:
            h = cur.execute("select count(*) from judgments_fts where judgments_fts match ?",
                            (q,)).fetchone()[0]
            print(f"  match({q!r}) = {h}")
        except sqlite3.Error as e:
            print(f"  match({q!r}) ERR {e}")

    print("== 抽样完整性（200 条）==")
    maxid = cur.execute("select max(rowid) from judgments").fetchone()[0]
    if maxid:
        import random
        random.seed(11)
        ids = random.sample(range(1, maxid + 1), min(200, maxid))
        q = ",".join("?" * len(ids))
        rows = cur.execute(
            f"select title, full_text from judgments where rowid in ({q})", ids).fetchall()
        filled = sum(1 for t, f in rows if t)
        print(f"  title 非空 {filled}/{len(rows)}")
        ufffd = sum(1 for t, f in rows if f and "\ufffd" in f)
        print(f"  含 U+FFFD 行 {ufffd}/{len(rows)}（源数据损伤，非入库问题）")

    if args.quick_check:
        t = time.perf_counter()
        res = cur.execute("pragma quick_check").fetchone()[0]
        print(f"== quick_check: {res} ({time.perf_counter()-t:.1f}s) ==")
        ok &= res == "ok"

    con.close()
    print("RESULT " + ("ALL_PASS" if ok else "HAS_FAIL"))
    return 0 if ok else 3


if __name__ == "__main__":
    sys.exit(main())
