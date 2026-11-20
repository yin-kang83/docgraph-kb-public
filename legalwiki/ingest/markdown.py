"""Markdown ingest for legal documents: Law -> Chapter -> Article -> Chunk.

MVP scope:
- heading-aware (H1=Law, H2=Chapter, H3+=Article)
- deterministic ids
- no citation/amendment extraction yet
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

from ..graph import store

HEADING = re.compile(r"^(#{1,6})\s+(.*)$")


def _id(prefix: str, *parts: str) -> str:
    h = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:10]
    return f"{prefix}-{h}"


def _chunks(text: str, max_chars: int = 600) -> list[str]:
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    out, buf = [], ""
    for p in paras:
        if buf and len(buf) + len(p) + 2 > max_chars:
            out.append(buf)
            buf = p
        else:
            buf = f"{buf}\n\n{p}" if buf else p
    if buf:
        out.append(buf)
    return out


def ingest_markdown(conn, path: str | Path, law_id: str | None = None) -> dict:
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    law_id = law_id or _id("LAW", str(path.resolve()))
    title = path.stem
    nodes: list[tuple[str, str, str, int]] = []  # id,type,label,level
    current = law_id
    chunk_no = 0
    buf: list[str] = []

    def flush():
        nonlocal buf, chunk_no
        body = "\n".join(buf).strip()
        if not body:
            return
        for piece in _chunks(body):
            chunk_no += 1
            cid = _id("CH", law_id, str(chunk_no))
            store.add_chunk(conn, cid, current, piece)
            store.add_edge(conn, current, cid, "CONTAINS")
        buf = []

    store.add_node(conn, law_id, "Law", title, str(path))
    for line in text.splitlines():
        m = HEADING.match(line)
        if m:
            flush()
            level, heading = len(m.group(1)), m.group(2).strip()
            if level == 1:
                title = heading
                store.add_node(conn, law_id, "Law", title, str(path))
                current = law_id
            else:
                ntype = "Chapter" if level == 2 else "Article"
                nid = _id("N", law_id, str(len(nodes) + 1), heading)
                store.add_node(conn, nid, ntype, heading, str(path))
                parent = law_id
                for prev_id, _, _, prev_level in reversed(nodes):
                    if prev_level < level:
                        parent = prev_id
                        break
                store.add_edge(conn, parent, nid, "CONTAINS")
                nodes.append((nid, ntype, heading, level))
                current = nid
            continue
        buf.append(line)
    flush()
    conn.commit()
    return {"law": law_id, "sections": len(nodes), "chunks": chunk_no}


def ingest_dir(conn, root: str | Path, pattern: str = "*.md") -> list[dict]:
    root = Path(root)
    files = [root] if root.is_file() else sorted(root.rglob(pattern))
    return [ingest_markdown(conn, p) for p in files]
