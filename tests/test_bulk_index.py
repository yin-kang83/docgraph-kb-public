import csv, io, zipfile
from legalwiki.graph import store
from legalwiki.ingest import bulk_index


def _zip(tmp_path):
    rows = [
        {"案号": "（2020）测1号", "案件名称": "甲诉乙合同纠纷", "法院": "测试法院",
         "所属地区": "测试区", "案件类型": "民事案件", "审理程序": "一审",
         "裁判日期": "2020-01-01", "案由": "合同纠纷",
         "法律依据": "《合同法》第一条", "全文": "原告甲与被告乙签订合同。" * 20},
        {"案号": "（2020）测2号", "案件名称": "丙诉丁侵权纠纷", "法院": "测试法院",
         "所属地区": "测试区", "案件类型": "民事案件", "审理程序": "一审",
         "裁判日期": "2020-02-01", "案由": "侵权纠纷",
         "法律依据": "", "全文": "被告不得侵害他人权益。" * 20},
        {"案号": "（2020）测1号", "案件名称": "重复", "法院": "测试法院",
         "所属地区": "测试区", "案件类型": "民事案件", "审理程序": "一审",
         "裁判日期": "2020-01-01", "案由": "合同纠纷", "法律依据": "",
         "全文": "原告甲与被告乙签订合同。" * 20},
    ]
    buf = io.StringIO(); w = csv.DictWriter(buf, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    p = tmp_path / "cases.zip"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("cases.csv", buf.getvalue().encode("utf-8-sig"))
    return p


def test_index_zip(tmp_path):
    conn = store.init_db(tmp_path / "test.db")
    s = bulk_index.index_zip(conn, _zip(tmp_path))
    assert s["ok"] == 2 and s["duplicates"] == 1
    assert conn.execute("SELECT COUNT(*) n FROM judgments").fetchone()["n"] == 2
    rows = conn.execute("SELECT judgment_id FROM judgments_fts WHERE judgments_fts MATCH ?", ("合同纠纷",)).fetchall()
    assert rows


def test_large_field_csv(tmp_path):
    """全文超过 CSV 默认字段上限（131072 字节）时不应崩。"""
    big = "长" * 200_000  # UTF-8 约 600 KB
    rows = [{"案号": "（2024）大1号", "案件名称": "大字段测试", "法院": "测试法院",
             "所属地区": "测试区", "案件类型": "民事案件", "审理程序": "一审",
             "裁判日期": "2024-01-01", "案由": "测试", "法律依据": "", "全文": big}]
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(rows[0]))
    w.writeheader(); w.writerows(rows)
    p = tmp_path / "big.zip"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("big.csv", buf.getvalue().encode("utf-8-sig"))
    conn = store.init_db(tmp_path / "big.db")
    s = bulk_index.index_zip(conn, p, build_fts_index=False)
    assert s["ok"] == 1
    n = conn.execute("SELECT LENGTH(full_text) n FROM judgments").fetchone()["n"]
    assert n > 131072


def test_build_fts_full_text(tmp_path):
    """--full-text：正文可检索；默认仅标题时正文词查不到。"""
    conn = store.init_db(tmp_path / "test.db")
    bulk_index.index_zip(conn, _zip(tmp_path), build_fts_index=False)
    n = bulk_index.build_fts(conn, full_text=True)
    assert n == 2
    # "签订合同" 只出现在第一条的全文里（第三条是它的重复、不入库），标题里没有
    rows = conn.execute(
        "SELECT judgment_id FROM judgments_fts WHERE judgments_fts MATCH ?",
        ("签订合同",)).fetchall()
    assert len(rows) == 1


def test_build_fts_title_only_default(tmp_path):
    """默认（标题-only）：正文词查不到，标题词可查到。"""
    conn = store.init_db(tmp_path / "test.db")
    bulk_index.index_zip(conn, _zip(tmp_path), build_fts_index=False)
    n = bulk_index.build_fts(conn)
    assert n == 2
    body = conn.execute(
        "SELECT judgment_id FROM judgments_fts WHERE judgments_fts MATCH ?",
        ("签订合同",)).fetchall()
    assert body == []
    title = conn.execute(
        "SELECT judgment_id FROM judgments_fts WHERE judgments_fts MATCH ?",
        ("合同纠纷",)).fetchall()
    assert title
