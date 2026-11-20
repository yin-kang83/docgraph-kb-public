from legalwiki.graph import store
from legalwiki.ingest import titles


def test_build_titles(tmp_path):
    conn = store.init_db(tmp_path / "t.db")
    conn.execute("INSERT INTO judgments (id,title,full_text) VALUES ('a','租赁合同纠纷','x')")
    conn.execute("INSERT INTO judgments (id,title,full_text) VALUES ('b','买卖合同纠纷','y')")
    conn.commit()
    assert titles.build_titles(conn) == 2
    rows = conn.execute("SELECT id FROM judgment_titles WHERE title LIKE '%租赁%'").fetchall()
    assert rows[0][0] == "a"
