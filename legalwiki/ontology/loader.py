"""Load curated legal concepts (YAML) into the graph.

Source policy: every concept must carry source/article/source_url.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import yaml

from ..graph import store

REQUIRED = ("id", "term", "definition", "source", "article", "source_url", "jurisdiction", "effective_date")
RULE_REQUIRED = ("id", "rule", "statement", "source", "article", "source_url", "jurisdiction", "effective_date")


def _hid(prefix: str, *parts: str) -> str:
    return prefix + "-" + hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:12]


def load_yaml(path: Path) -> list[dict]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data or []


def validate(concepts: list[dict], required=REQUIRED) -> list[str]:
    errors, ids = [], set()
    for i, c in enumerate(concepts):
        for k in required:
            if not c.get(k):
                errors.append(f"#{i} missing {k}")
        if c.get("id") in ids:
            errors.append(f"duplicate id {c.get('id')}")
        ids.add(c.get("id"))
        url = str(c.get("source_url", ""))
        if not (url.startswith("http://") or url.startswith("https://")):
            errors.append(f"{c.get('id')} bad source_url")
        if not str(c.get("article", "")).startswith("第"):
            errors.append(f"{c.get('id')} article should start with 第")
    return errors


def load_rules(conn, root: Path) -> int:
    path = root / "validity_rules.yml"
    if not path.exists():
        return 0
    rules = load_yaml(path)
    errors = validate(rules, RULE_REQUIRED)
    if errors:
        raise ValueError("validity rule validation failed: " + "; ".join(errors[:10]))
    for r in rules:
        rid = r["id"]
        store.add_node(conn, rid, "ValidityRule", r["rule"], meta={
            "statement": r["statement"], "source": r["source"], "article": r["article"],
            "source_quote": r.get("source_quote", ""), "source_url": r["source_url"],
            "jurisdiction": r["jurisdiction"], "effective_date": str(r["effective_date"]),
        })
        aid = _hid("ART", r["source"], r["article"])
        store.add_node(conn, aid, "Article", f"《{r['source']}》{r['article']}", meta={
            "source": r["source"], "article": r["article"], "source_url": r["source_url"],
        }, effective_from=str(r["effective_date"]), status="in_force")
        store.add_edge(conn, rid, aid, "DEFINED_BY")
    conn.commit()
    return len(rules)


def load(conn, root: str | Path) -> dict:
    root = Path(root)
    concepts = load_yaml(root / "concepts.yml")
    errors = validate(concepts)
    if errors:
        raise ValueError("ontology validation failed: " + "; ".join(errors[:10]))
    articles = 0
    for c in concepts:
        cid = c["id"]
        store.add_node(conn, cid, "Concept", c["term"], meta={
            "definition": c["definition"],
            "definition_type": c.get("definition_type", "paraphrase"),
            "source": c["source"],
            "article": c["article"],
            "source_quote": c.get("source_quote", ""),
            "source_url": c["source_url"],
            "jurisdiction": c["jurisdiction"],
            "effective_date": str(c["effective_date"]),
        }, effective_from=str(c["effective_date"]), status="in_force")
        aid = _hid("ART", c["source"], c["article"])
        store.add_node(conn, aid, "Article", f"《{c['source']}》{c['article']}", meta={
            "source": c["source"], "article": c["article"], "source_url": c["source_url"],
        })
        store.add_edge(conn, cid, aid, "DEFINED_BY")
        articles += 1
    conn.commit()
    rules = load_rules(conn, root)
    return {"concepts": len(concepts), "rules": rules, "articles": articles + rules}
