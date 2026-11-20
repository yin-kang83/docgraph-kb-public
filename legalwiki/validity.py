"""Check whether a cited law was in force on the judgment date.

This is a first-pass registry: only laws with confirmed dates are listed.
Unknown laws are reported as unknown, never assumed valid.
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import yaml

from .time import norm_status

DEFAULT = Path(__file__).resolve().parents[1] / "ontology" / "law_versions.yml"
YEAR = re.compile(r"[（(]\d{4}年[）)]")


def normalize_law(name: str) -> str:
    s = (name or "").strip()
    s = YEAR.sub("", s)
    s = s.replace("中华人民共和国", "")
    s = re.sub(r"\s+", "", s)
    return s


def load_versions(path: str | Path | None = None) -> dict[str, dict]:
    data = yaml.safe_load(Path(path or DEFAULT).read_text(encoding="utf-8")) or []
    out = {}
    for item in data:
        if item.get("status") == "repealed" and not item.get("effective_to"):
            raise ValueError(f"repealed law lacks effective_to: {item.get('law')}")
        keys = [item["law"], *item.get("aliases", [])]
        for k in keys:
            out[normalize_law(k)] = item
    # validate repealed_by targets
    for item in data:
        target = item.get("repealed_by")
        if target and normalize_law(target) not in out:
            raise ValueError(f"repealed_by target not registered: {target}")
    return out


def check_citations(conn: sqlite3.Connection, limit: int | None = None,
                    versions: dict[str, dict] | None = None) -> dict:
    versions = versions or load_versions()
    sql = """SELECT c.judgment_id, c.law, j.judgment_date
             FROM judgment_citations c JOIN judgments j ON j.id = c.judgment_id
             WHERE c.law IS NOT NULL"""
    if limit:
        sql += f" LIMIT {int(limit)}"
    counts: dict[str, int] = {}
    samples: list[dict] = []
    for jid, law, jd in conn.execute(sql):
        item = versions.get(normalize_law(law))
        if item is None:
            status = "not_in_registry"
        elif not item.get("effective_from") or (item.get("status") == "repealed" and not item.get("effective_to")):
            status = "unknown_dates"
        else:
            status = norm_status(item, jd)
        counts[status] = counts.get(status, 0) + 1
        if status in ("not_yet_effective", "repealed") and len(samples) < 10:
            samples.append({"judgment_id": jid, "law": law,
                            "judgment_date": jd, "status": status})
    return {"counts": counts, "samples": samples}
