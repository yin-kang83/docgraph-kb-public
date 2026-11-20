from legalwiki.graph import queries, store
from legalwiki.ingest import claims, markdown


def _md(tmp_path):
    p = tmp_path / "law.md"
    p.write_text(
        "# 测试法\n\n## 第一章 总则\n\n### 第一条\n\n当事人应当依照本法履行义务。\n\n"
        "### 第二条\n\n任何组织不得非法干预。\n",
        encoding="utf-8",
    )
    return p


def test_markdown_law(tmp_path):
    conn = store.init_db(tmp_path / "test.db")
    stats = markdown.ingest_markdown(conn, _md(tmp_path))
    assert stats["sections"] == 3
    assert stats["chunks"] >= 2
    assert queries.search_chunks(conn, "履行义务")


def test_legal_claims(tmp_path):
    conn = store.init_db(tmp_path / "test.db")
    markdown.ingest_markdown(conn, _md(tmp_path))
    stats = claims.extract_all(conn)
    assert stats["claims"] >= 2
    row = conn.execute("SELECT id FROM nodes WHERE type='Claim' LIMIT 1").fetchone()
    chain = queries.evidence_chain(conn, row["id"])
    assert chain and chain[0]["role"] == "norm"
