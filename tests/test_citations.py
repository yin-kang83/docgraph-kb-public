from legalwiki.graph import store
from legalwiki.ingest import citations


def test_build_citations(tmp_path):
    conn = store.init_db(tmp_path / "c.db")
    conn.execute("INSERT INTO judgments (id,basis,full_text,title) VALUES (?,?,?,?)",
                 ("j1", "《中华人民共和国合同法》:第一百一十条,第六十一条；《民法典》:第五百条", "x", "t1"))
    conn.execute("INSERT INTO judgments (id,basis,full_text,title) VALUES (?,?,?,?)",
                 ("j2", "无", "x", "t2"))
    conn.commit()
    s = citations.build_citations(conn)
    assert s["citations"] == 3
    assert s["judgments"] == 1
    laws = [r[0] for r in conn.execute("SELECT law FROM judgment_citations WHERE law IS NOT NULL ORDER BY law")]
    assert laws == ["中华人民共和国合同法", "民法典"]
