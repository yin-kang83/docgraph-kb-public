# -*- coding: utf-8 -*-
"""可插拔 embedder：fake（确定性哈希，测试）/ qwen（DashScope 接口）/ local（可选）。

测试只使用 fake；qwen 不在测试中真调，local 未安装则明确 unavailable。
"""
from __future__ import annotations

import hashlib
import json
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Sequence

import numpy as np


class EmbedderError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.message = message


class EmbedderUnavailable(EmbedderError):
    pass


class BaseEmbedder(ABC):
    name: str = "base"
    dim: int = 0

    @abstractmethod
    def embed(self, texts: Sequence[str]) -> np.ndarray:
        """返回 shape=(n, dim) 的 float32 向量。"""


def text_for_judgment(title: str | None, full_text: str | None, max_chars: int = 1000) -> str:
    """只对标题 + 前 1000 字做向量（task-84 边界）。"""
    title = str(title or "").strip()
    full = str(full_text or "")
    return (title + "\n" + full[:max_chars]).strip()


class FakeEmbedder(BaseEmbedder):
    """确定性哈希向量：同文本同向量；不联网、无随机数。"""

    name = "fake-hash-v1"

    def __init__(self, dim: int = 64):
        if dim <= 0:
            raise ValueError("dim 必须 > 0")
        self.dim = int(dim)

    def _one(self, text: str) -> np.ndarray:
        vec = np.zeros(self.dim, dtype=np.float32)
        text = str(text or "")
        grams = [text[i:i + 3] for i in range(max(1, len(text) - 2))]
        if not grams:
            grams = [text or "<empty>"]
        for gram in grams:
            digest = hashlib.blake2b(gram.encode("utf-8"), digest_size=8).digest()
            index = int.from_bytes(digest[:4], "little") % self.dim
            sign = 1.0 if digest[4] & 1 else -1.0
            vec[index] += sign
        norm = float(np.linalg.norm(vec))
        if norm == 0:
            vec[0] = 1.0
            norm = 1.0
        return vec / norm

    def embed(self, texts: Sequence[str]) -> np.ndarray:
        rows = [self._one(text) for text in texts]
        if not rows:
            return np.zeros((0, self.dim), dtype=np.float32)
        return np.vstack(rows).astype(np.float32)


class QwenEmbedder(BaseEmbedder):
    """DashScope text-embedding 接口；只留接口，测试不真调。"""

    name = "qwen-text-embedding"

    def __init__(self, model: str = "text-embedding-v3", dim: int = 1024,
                 endpoint: str | None = None, timeout: int = 30):
        self.model = model
        self.dim = int(dim)
        self.endpoint = endpoint or os.environ.get(
            "QWEN_EMBEDDING_URL",
            "https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings",
        )
        self.timeout = timeout

    def _key(self) -> str:
        key = os.environ.get("QWEN_KEY", "").strip()
        if key:
            return key
        # 只从环境变量取路径，不在代码里写死本机路径
        keyfile_env = os.environ.get("QWEN_KEYFILE", "").strip()
        if keyfile_env:
            keyfile = Path(keyfile_env)
            if keyfile.is_file():
                key = keyfile.read_text(encoding="utf-8").strip()
        if not key:
            raise EmbedderError("E_QWEN_KEY", "缺少 QWEN_KEY（或 QWEN_KEYFILE）")
        return key

    def embed(self, texts: Sequence[str]) -> np.ndarray:
        import urllib.request

        key = self._key()  # 无 key 立即失败，不发起请求
        body = {"model": self.model, "input": list(texts), "encoding_format": "float"}
        request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except EmbedderError:
            raise
        except Exception as exc:  # noqa: BLE001 - 明确失败
            raise EmbedderError("E_QWEN_HTTP", f"embedding HTTP 失败：{exc}") from exc
        try:
            vectors = [item["embedding"] for item in sorted(payload["data"],
                                                             key=lambda x: x["index"])]
        except (KeyError, TypeError) as exc:
            raise EmbedderError("E_QWEN_RESPONSE", "embedding 响应缺少 data[].embedding") from exc
        matrix = np.asarray(vectors, dtype=np.float32)
        if matrix.ndim != 2 or matrix.shape[0] != len(texts):
            raise EmbedderError("E_QWEN_RESPONSE", f"embedding 维度异常：{matrix.shape}")
        self.dim = int(matrix.shape[1])
        return matrix


class LocalEmbedder(BaseEmbedder):
    """sentence-transformers 可选；未安装明确 unavailable。"""

    name = "local-sentence-transformers"

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
        except Exception as exc:  # noqa: BLE001
            raise EmbedderUnavailable("E_LOCAL_UNAVAILABLE",
                                      f"sentence-transformers 未安装：{exc}") from exc
        self._model = SentenceTransformer(model_name)
        self.dim = int(self._model.get_sentence_embedding_dimension())

    @staticmethod
    def available() -> bool:
        try:
            import sentence_transformers  # type: ignore  # noqa: F401
            return True
        except Exception:  # noqa: BLE001
            return False

    def embed(self, texts: Sequence[str]) -> np.ndarray:
        vectors = self._model.encode(list(texts), normalize_embeddings=True)
        return np.asarray(vectors, dtype=np.float32)


def make_embedder(backend: str, **kwargs) -> BaseEmbedder:
    backend = str(backend or "").lower()
    if backend == "fake":
        return FakeEmbedder(**kwargs)
    if backend == "qwen":
        return QwenEmbedder(**kwargs)
    if backend == "local":
        return LocalEmbedder(**kwargs)
    raise EmbedderError("E_BACKEND", f"未知 embedding 后端：{backend}")
