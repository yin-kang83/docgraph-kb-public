# -*- coding: utf-8 -*-
"""demo_vector.py —— fake embedder + hybrid retrieval 本地 demo（不联网）。

只用临时 SQLite 和 5 条合成判例；不访问 E: 的全量 2013 库。
"""
from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legalwiki.graph import store  # noqa: E402
from legalwiki.retrieval.embedder import FakeEmbedder, text_for_judgment  # noqa: E402
from legalwiki.retrieval.hybrid import search_hybrid  # noqa: E402
from legalwiki.retrieval.vector_store import embed_judgments  # noqa: E402

ROWS = [
    ("J1", "房屋租赁合同纠纷", "合同约定租金每年十万元，承租人逾期支付租金。"),
    ("J2", "买卖合同纠纷", "买方未按约支付货款，卖方请求违约金。"),
    ("J3", "劳动合同纠纷", "用人单位解除劳动合同，劳动者请求赔偿金。"),
    ("J4", "民间借贷纠纷", "借款人未按期还款，出借人请求本金及利息。"),
    ("J5", "房屋买卖合同纠纷", "卖方一房二卖，买方请求继续履行合同。"),
]


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "demo.db"
        conn = store.init_db(db)
        for jid, title, full in ROWS:
            conn.execute("INSERT INTO judgments (id,title,full_text) VALUES (?,?,?)",
                         (jid, title, full))
            conn.execute("INSERT INTO judgments_fts (judgment_id,title,full_text) VALUES (?,?,?)",
                         (jid, title, full))
        conn.commit()
        stats = embed_judgments(conn, FakeEmbedder(dim=32), limit=5000, backend="fake")
        rows = search_hybrid(conn, "房屋租赁合同", FakeEmbedder(dim=32), limit=3)
        print(json.dumps({"embed": stats, "query": "房屋租赁合同", "hits": rows},
                         ensure_ascii=False, indent=2))
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
