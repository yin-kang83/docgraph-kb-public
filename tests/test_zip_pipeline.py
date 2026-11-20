import csv
import io
import zipfile

from legalwiki.graph import store
from legalwiki.ingest import judgments_zip


def _zip(tmp_path):
    p = tmp_path / "2013.zip"
    rows = [
        {"案号": "（2020）测1号", "案件名称": "甲诉乙", "法院": "测试法院",
         "所属地区": "测试区", "案件类型": "民事案件", "审理程序": "一审",
         "裁判日期": "2020-01-01", "案由": "合同纠纷",
         "法律依据": "《合同法》第一条", "全文": "原告甲与被告乙签订合同。" * 10},
        {"案号": "（2020）测2号", "案件名称": "丙诉丁", "法院": "测试法院",
         "所属地区": "测试区", "案件类型": "民事案件", "审理程序": "一审",
         "裁判日期": "2020-13-01", "案由": "侵权纠纷",
         "法律依据": "《民法典》第二条", "全文": "被告不得侵害他人权益。" * 10},
        {"案号": "（2020）测1号", "案件名称": "甲诉乙重复", "法院": "测试法院",
         "所属地区": "测试区", "案件类型": "民事案件", "审理程序": "一审",
         "裁判日期": "2020-01-01", "案由": "合同纠纷",
         "法律依据": "", "全文": "原告甲与被告乙签订合同。" * 10},
        {"案号": "", "案件名称": "", "法院": "", "全文": ""},
    ]
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("2013_01.csv", buf.getvalue().encode("utf-8-sig"))
    return p


def test_clean_row():
    c, errors, warns = judgments_zip.clean_row({
        "案号": "（2020）测1号", "案件名称": "甲诉乙", "法院": "测试法院",
        "裁判日期": "2020/1/1", "法律依据": "《合同法》第一条",
        "全文": "原告甲与被告乙签订合同。" * 10,
    })
    assert not errors
    assert c["judgment_date"] == "2020-01-01"
    assert c["basis"][0]["law"] == "合同法"
    assert "empty_legal_basis" not in warns


def test_zip_dry_run(tmp_path):
    conn = store.init_db(tmp_path / "test.db")
    s = judgments_zip.ingest_zip(conn, _zip(tmp_path), dry_run=True)
    assert s["rows_read"] == 4
    assert s["rows_ok"] == 3  # dry-run 不查重：good + invalid-date + duplicate
    assert s["rows_reject"] == 1
    assert not conn.execute("SELECT COUNT(*) n FROM nodes").fetchone()["n"]


def test_zip_ingest_and_dedup(tmp_path):
    conn = store.init_db(tmp_path / "test.db")
    s = judgments_zip.ingest_zip(conn, _zip(tmp_path), db_path=tmp_path / "test.db")
    assert s["rows_ok"] == 2
    assert s["duplicates"] == 1
    assert s["chunks"] >= 2
    assert conn.execute("SELECT COUNT(*) n FROM rejects").fetchone()["n"] == 1
    assert conn.execute("SELECT COUNT(*) n FROM quality_flags").fetchone()["n"] >= 1
