"""Legal time: which norm applies as of a given date."""
from __future__ import annotations

from datetime import date


def _d(s: str | None):
    if not s:
        return None
    try:
        return date.fromisoformat(str(s)[:10])
    except ValueError:
        return None


def norm_status(norm: dict, as_of: str | None) -> str:
    """Return in_force / not_yet_effective / expired / repealed / unknown."""
    d = _d(as_of)
    if d is None:
        return "unknown"
    start = _d(norm.get("effective_from"))
    end = _d(norm.get("effective_to"))
    if start is None:
        return "unknown"
    if d < start:
        return "not_yet_effective"
    if end is not None and d >= end:
        return "repealed" if norm.get("status") == "repealed" else "expired"
    if norm.get("status") == "repealed":
        return "unknown" if end is None else "in_force"
    return "in_force"


def applicable_norms(conn, case_id: str) -> list[dict]:
    rows = conn.execute(
        """SELECT n.*, e.as_of
           FROM edges e JOIN nodes n ON n.id = e.dst
           WHERE e.src = ? AND e.type = 'CITES'""",
        (case_id,),
    ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["temporal_status"] = norm_status(d, d.get("as_of"))
        out.append(d)
    return out
