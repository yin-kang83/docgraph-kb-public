# -*- coding: utf-8 -*-
"""judgment embeddings + hybrid retrieval 测试（fake backend；不联网、不调真模型）。"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legalwiki import cli  # noqa: E402
from legalwiki.graph import store  # noqa: E402
from legalwiki.retrieval import embedder as embedder_mod  # noqa: E402
from legalwiki.retrieval import hybrid, vector_store  # noqa: E402
from legalwiki.retrieval.embedder import (  # noqa: E402
    BaseEmbedder, EmbedderError, EmbedderUnavailable, FakeEmbedder,
    LocalEmbedder, QwenEmbedder, make_embedder, text_for_judgment,
)

SCHEMA = ROOT / "schema.sql"


def make_db(tmp_path: Path, rows: list[tuple[str, str, str]]) -> tuple[sqlite3.Connection, Path]:
    db = tmp_path / "legal.db"
    conn = sqlite3.connect(db)
    conn.executescript(SCHEMA.read_text(encoding="utf-8"))
    for jid, title, full in rows:
        conn.execute(
            "INSERT INTO judgments (id,title,full_text) VALUES (?,?,?)", (jid, title, full))
        conn.execute(
            "INSERT INTO judgments_fts (judgment_id,title,full_text) VALUES (?,?,?)",
            (jid, title, full))
    conn.commit()
    return conn, db


def sample_rows():
    return [
        ("J1", "房屋租赁合同纠纷", "合同约定租金每年十万元，承租人逾期支付。"),
        ("J2", "买卖合同纠纷", "买方未按约支付货款，卖方请求违约金。"),
        ("J3", "劳动合同纠纷", "用人单位解除劳动合同，劳动者请求赔偿。"),
    ]


# ══════════════════ fake embedder ══════════════════
def test_fake_embedder_deterministic():
    emb = FakeEmbedder(dim=16)
    a = emb.embed(["合同纠纷"])
    b = emb.embed(["合同纠纷"])
    assert np.array_equal(a, b)


def test_fake_embedder_dim_and_shape():
    emb = FakeEmbedder(dim=32)
    matrix = emb.embed(["a", "b", "c"])
    assert matrix.shape == (3, 32)
    assert matrix.dtype == np.float32


def test_fake_embedder_normalized():
    matrix = FakeEmbedder(dim=8).embed(["合同纠纷", "买卖合同"])
    norms = np.linalg.norm(matrix, axis=1)
    assert np.allclose(norms, 1.0, atol=1e-5)


def test_fake_embedder_different_text_differs():
    emb = FakeEmbedder(dim=16)
    assert not np.array_equal(emb.embed(["合同"])[0], emb.embed(["侵权"])[0])


def test_text_for_judgment_title_and_1000_chars():
    text = text_for_judgment("标题", "甲" * 2000)
    assert text.startswith("标题")
    assert len(text) <= len("标题") + 1 + 1000


def test_make_embedder_unknown_backend():
    with pytest.raises(EmbedderError):
        make_embedder("nope")


def test_qwen_embedder_missing_key_no_network(monkeypatch, tmp_path):
    monkeypatch.delenv("QWEN_KEY", raising=False)
    monkeypatch.setenv("QWEN_KEYFILE", str(tmp_path / "missing.key"))
    emb = QwenEmbedder(dim=8)
    with pytest.raises(EmbedderError) as exc:
        emb.embed(["合同"])
    assert exc.value.code == "E_QWEN_KEY"


def test_local_embedder_optional():
    if LocalEmbedder.available():
        pytest.skip("sentence-transformers 已安装；本测试只验证未安装路径")
    with pytest.raises(EmbedderUnavailable):
        LocalEmbedder()


# ══════════════════ 存取/余弦 ══════════════════
def test_schema_has_embedding_tables(tmp_path):
    conn, _ = make_db(tmp_path, [])
    tables = {row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert "judgment_embeddings" in tables
    assert "embedding_runs" in tables


def test_pack_unpack_roundtrip():
    vector = np.array([1.0, 0.0, -2.0], dtype=np.float32)
    packed = vector_store.pack_vector(vector)
    assert np.array_equal(vector_store.unpack_vector(packed, 3), vector)


def test_upsert_get_embedding(tmp_path):
    conn, _ = make_db(tmp_path, sample_rows())
    vector = np.array([0.1, 0.2, 0.3], dtype=np.float32)
    vector_store.upsert_embedding(conn, "J1", "fake", vector)
    conn.commit()
    got = vector_store.get_embedding(conn, "J1", "fake")
    assert np.allclose(got, vector)


def test_cosine_top_k_ordering():
    matrix = np.array([[1.0, 0.0], [0.9, 0.1], [0.0, 1.0]], dtype=np.float32)
    hits = vector_store.cosine_top_k([1.0, 0.0], matrix, ["a", "b", "c"], 2)
    assert [hit[0] for hit in hits] == ["a", "b"]
    assert hits[0][1] > hits[1][1]


def test_vector_search_empty(tmp_path):
    conn, _ = make_db(tmp_path, sample_rows())
    assert vector_store.search_vectors(conn, np.ones(4), "fake", 5) == []


def test_embed_judgments_limit_and_idempotent(tmp_path):
    conn, _ = make_db(tmp_path, sample_rows())
    emb = FakeEmbedder(dim=8)
    first = vector_store.embed_judgments(conn, emb, limit=2)
    assert first["rows"] == 2
    assert conn.execute("SELECT COUNT(*) FROM judgment_embeddings").fetchone()[0] == 2
    second = vector_store.embed_judgments(conn, emb, limit=2)
    assert second["rows"] == 1  # 只剩 1 条未嵌入


def test_embed_judgments_truncates_text(tmp_path):
    seen = []

    class RecordingEmbedder(BaseEmbedder):
        name = "rec"
        dim = 4

        def embed(self, texts):
            seen.extend(texts)
            return np.ones((len(texts), 4), dtype=np.float32)

    conn, _ = make_db(tmp_path, [("J1", "t", "甲" * 1500)])
    vector_store.embed_judgments(conn, RecordingEmbedder(), limit=10)
    assert len(seen[0]) <= len("t") + 1 + 1000


# ══════════════════ FTS / hybrid ══════════════════
def test_fts_search_matches(tmp_path):
    conn, _ = make_db(tmp_path, sample_rows())
    hits = hybrid.fts_search(conn, "合同", 10)
    assert hits
    assert hits[0]["judgment_id"] in {"J1", "J3"}


def test_rrf_fuse_prefers_shared_result():
    fused = hybrid.rrf_fuse({"fts": ["a", "b"], "vector": ["b", "c"]})
    assert fused[0][0] == "b"


def test_weighted_fuse_weights():
    fused = hybrid.weighted_fuse({"fts": ["a"], "vector": ["b"]}, {"fts": 2.0, "vector": 1.0})
    assert fused[0][0] == "a"


def test_hybrid_combines_fts_and_vector(tmp_path):
    conn, _ = make_db(tmp_path, sample_rows())
    emb = FakeEmbedder(dim=32)
    vector_store.embed_judgments(conn, emb, limit=10)
    rows = hybrid.search_hybrid(conn, "房屋租赁合同", emb, limit=3, fts_limit=10, vector_limit=10)
    assert rows
    assert any("vector" in row["sources"] for row in rows)
    assert any("fts" in row["sources"] for row in rows)


def test_hybrid_degrades_without_vectors(tmp_path):
    conn, _ = make_db(tmp_path, sample_rows())
    rows = hybrid.search_hybrid(conn, "合同", FakeEmbedder(dim=8), limit=3)
    assert rows
    assert all("vector" not in row["sources"] for row in rows)


def test_hybrid_empty_db(tmp_path):
    conn, _ = make_db(tmp_path, [])
    assert hybrid.search_hybrid(conn, "合同", FakeEmbedder(dim=8), limit=3) == []


def test_fts_empty_query(tmp_path):
    conn, _ = make_db(tmp_path, sample_rows())
    assert hybrid.fts_search(conn, "", 10) == []


# ══════════════════ CLI / schema ══════════════════
def test_cli_embed_then_hybrid(tmp_path, capsys):
    conn, db = make_db(tmp_path, sample_rows())
    conn.close()
    assert cli.main(["embed-judgments", "--db", str(db), "--limit", "3", "--backend", "fake"]) == 0
    capsys.readouterr()
    assert cli.main(["search-hybrid", "--db", str(db), "--q", "合同", "--limit", "3"]) == 0
    output = capsys.readouterr().out
    rows = json.loads(output)
    assert rows
    assert "judgment_id" in rows[0]


def test_schema_sql_contains_vector_tables():
    text = SCHEMA.read_text(encoding="utf-8")
    assert "judgment_embeddings" in text
    assert "embedding_runs" in text
    assert "vector BLOB" in text
