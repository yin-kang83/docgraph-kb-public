from legalwiki import time
from legalwiki.graph import store


def _norm(conn, nid="N1", start="2021-01-01", status="in_force"):
    store.add_node(conn, nid, "Norm", "测试规范", effective_from=start, status=status)


def test_norm_status():
    assert time.norm_status({"effective_from": "2021-01-01", "status": "in_force"}, "2020-01-01") == "not_yet_effective"
    assert time.norm_status({"effective_from": "2021-01-01", "status": "in_force"}, "2022-01-01") == "in_force"
    assert time.norm_status({"effective_from": "2021-01-01", "status": "repealed"}, "2022-01-01") == "unknown"
    assert time.norm_status({"effective_from": "2021-01-01", "status": "in_force"}, None) == "unknown"


def test_applicable_norms(tmp_path):
    conn = store.init_db(tmp_path / "test.db")
    _norm(conn)
    store.add_node(conn, "C1", "Case", "旧案")
    store.add_edge(conn, "C1", "N1", "CITES", as_of="2020-01-01")
    rows = time.applicable_norms(conn, "C1")
    assert rows[0]["temporal_status"] == "not_yet_effective"


def test_repealed_law_still_in_force_for_old_case():
    assert time.norm_status({"effective_from": "1999-10-01", "effective_to": "2021-01-01",
                             "status": "repealed"}, "2013-06-01") == "in_force"
    assert time.norm_status({"effective_from": "1999-10-01", "effective_to": "2021-01-01",
                             "status": "repealed"}, "2022-06-01") == "repealed"
