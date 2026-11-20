from legalwiki import validity
from legalwiki.graph import store


def test_normalize_law_preserves_amendment():
    assert validity.normalize_law("中华人民共和国合同法（1999年）") == "合同法"
    assert validity.normalize_law("刑法修正案（十一）") != validity.normalize_law("中华人民共和国刑法")


def test_check_citations_temporal(tmp_path):
    conn = store.init_db(tmp_path / "v.db")
    rows = [
        ("j1", "2013-06-01", "中华人民共和国合同法"),
        ("j2", "2022-06-01", "中华人民共和国合同法"),
        ("j3", "2013-06-01", "中华人民共和国民法典"),
        ("j4", "2013-06-01", "某未收录法"),
        ("j5", None, "中华人民共和国合同法"),
    ]
    for jid, jd, law in rows:
        conn.execute("INSERT INTO judgments (id,title,full_text,judgment_date) VALUES (?,?,?,?)",
                     (jid, jid, "x", jd))
        conn.execute("INSERT INTO judgment_citations (judgment_id,law,article,raw) VALUES (?,?,?,?)",
                     (jid, law, "第一条", law))
    conn.commit()
    versions = validity.load_versions()
    s = validity.check_citations(conn, versions=versions)
    assert s["counts"]["in_force"] == 1
    assert s["counts"]["repealed"] == 1
    assert s["counts"]["not_yet_effective"] == 1
    assert s["counts"]["not_in_registry"] == 1
    assert s["counts"]["unknown"] == 1


def test_repealed_without_end_rejected(tmp_path):
    p = tmp_path / "bad.yml"
    p.write_text("- law: X\n  effective_from: '2020-01-01'\n  status: repealed\n", encoding="utf-8")
    try:
        validity.load_versions(p)
    except ValueError as e:
        assert "effective_to" in str(e)
    else:
        raise AssertionError("expected ValueError")
