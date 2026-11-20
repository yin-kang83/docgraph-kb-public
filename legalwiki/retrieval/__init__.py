# -*- coding: utf-8 -*-
"""legalwiki.retrieval —— 判例向量/混合检索原型（task-84）。"""
from .embedder import (
    BaseEmbedder,
    EmbedderError,
    EmbedderUnavailable,
    FakeEmbedder,
    LocalEmbedder,
    QwenEmbedder,
    make_embedder,
    text_for_judgment,
)
from .vector_store import (
    cosine_top_k,
    embed_judgments,
    ensure_schema,
    pack_vector,
    search_vectors,
    unpack_vector,
    upsert_embedding,
)
from .hybrid import fts_search, rrf_fuse, search_hybrid, vector_search

__all__ = [
    "BaseEmbedder", "EmbedderError", "EmbedderUnavailable", "FakeEmbedder",
    "LocalEmbedder", "QwenEmbedder", "make_embedder", "text_for_judgment",
    "cosine_top_k", "embed_judgments", "ensure_schema", "pack_vector",
    "search_vectors", "unpack_vector", "upsert_embedding",
    "fts_search", "rrf_fuse", "search_hybrid", "vector_search",
]
