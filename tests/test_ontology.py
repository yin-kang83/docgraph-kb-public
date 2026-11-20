import yaml
from pathlib import Path

from legalwiki.graph import store
from legalwiki.ontology import loader

ONTOLOGY_DIR = Path(__file__).resolve().parents[1] / "ontology"


def test_load_ontology(tmp_path):
    conn = store.init_db(tmp_path / "test.db")
    stats = loader.load(conn, str(ONTOLOGY_DIR))
    assert stats["concepts"] == 10
    assert stats["rules"] == 6
    assert stats["articles"] == 16
    assert conn.execute("SELECT COUNT(*) n FROM nodes WHERE type='Concept'").fetchone()["n"] == 10
    assert conn.execute("SELECT COUNT(*) n FROM edges WHERE type='DEFINED_BY'").fetchone()["n"] == 16


def test_validate_rejects_missing_source():
    bad = [{"id": "x", "term": "x", "definition": "x", "source": "x",
            "article": "第一条", "source_url": "not-url", "jurisdiction": "CN",
            "effective_date": "2021-01-01"}]
    errs = loader.validate(bad)
    assert errs
    assert any("source_url" in e for e in errs)
