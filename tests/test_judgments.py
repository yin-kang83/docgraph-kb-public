import csv

from legalwiki.graph import queries, store
from legalwiki.ingest import judgments


def _csv(tmp_path):
    p = tmp_path / "cases.csv"
    rows = [
        {
            "案号": "（2020）测1号", "案件名称": "甲诉乙合同纠纷", "法院": "测试法院",
            "所属地区": "测试区", "案件类型": "民事案件", "审理程序": "一审",
            "裁判日期": "2020-01-01", "案由": "合同纠纷",
            "法律依据": "《合同法》第一条；《民法典》第二条",
            "全文": "原告甲与被告乙签订合同。被告应当承担违约责任。",
        },
        {
            "案号": "（2020）测2号", "案件名称": "丙诉丁侵权纠纷", "法院": "测试法院",
            "所属地区": "测试区", "案件类型": "民事案件", "审理程序": "二审",
            "裁判日期": "2020-02-01", "案由": "侵权纠纷",
            "法律依据": "",
            "全文": "被告不得侵害他人权益。",
        },
    ]
    with p.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    return p


def test_ingest_judgments(tmp_path):
    conn = store.init_db(tmp_path / "test.db")
    stats = judgments.ingest_csv(conn, _csv(tmp_path))
    assert stats["cases"] == 2
    assert stats["chunks"] >= 2
    assert stats["norms"] == 2
    rows = queries.search_chunks(conn, "违约责任")
    assert rows


def test_reingest_judgments(tmp_path):
    conn = store.init_db(tmp_path / "test.db")
    p = _csv(tmp_path)
    judgments.ingest_csv(conn, p)
    before = conn.execute("SELECT COUNT(*) n FROM nodes WHERE type='Case'").fetchone()["n"]
    judgments.ingest_csv(conn, p)
    after = conn.execute("SELECT COUNT(*) n FROM nodes WHERE type='Case'").fetchone()["n"]
    assert before == after
