"""Streaming ZIP -> cleaned judgment ingestion.

Design: INGEST_PIPELINE.md
- no full extraction
- raw rows / rejects / dedup / quality flags
- checkpoint per CSV member
"""
from __future__ import annotations

import csv
import hashlib
import html
import io
import json
import re
import sys
import unicodedata
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path

from ..graph import store

# 判决全文可能超过 CSV 默认字段上限（131072 字节）——2015 年语料实测会触发
# _csv.Error: field larger than field limit；这里放宽到平台安全上限。
try:
    csv.field_size_limit(min(sys.maxsize, 2**31 - 1))
except OverflowError:  # 32 位平台
    csv.field_size_limit(2**31 - 1)

REQUIRED = {"案号", "案件名称", "法院", "全文"}
DATE_RE = re.compile(r"(\d{4})[-/年.](\d{1,2})[-/月.](\d{1,2})")
BASIS_RE = re.compile(r"《([^》]+)》\s*(?:[:：]\s*(.+)|第\s*([^条]+?)\s*条)")
CTRL_RE = re.compile(r"[\u200b-\u200f\ufeff\x00-\x08\x0b\x0c\x0e-\x1f]")
TAG_RE = re.compile(r"<[^>]+>")


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def hid(prefix: str, *parts: str) -> str:
    return prefix + "-" + hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:12]


def clean_text(value: str) -> str:
    s = html.unescape(value or "")
    s = TAG_RE.sub(" ", s)
    s = CTRL_RE.sub("", s)
    s = unicodedata.normalize("NFKC", s)
    s = s.replace("\u3000", " ")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def parse_date(value: str):
    m = DATE_RE.search(value or "")
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
    except ValueError:
        return None


def parse_basis(value: str) -> list[dict]:
    out = []
    for item in re.split(r"[；;\n]", value or ""):
        item = clean_text(item)
        if not item:
            continue
        m = BASIS_RE.search(item)
        if m:
            article = (m.group(2) or m.group(3) or "").strip()
            out.append({"raw": item, "law": m.group(1), "article": article})
        else:
            out.append({"raw": item, "law": None, "article": None})
    return out


def clean_row(row: dict) -> tuple[dict | None, list[str], list[str]]:
    errors, warns = [], []
    case_no = unicodedata.normalize("NFKC", (row.get("案号") or "")).strip()
    title = clean_text(row.get("案件名称") or "")
    if not case_no and not title:
        errors.append("missing_case_no_and_title")
    court = clean_text(row.get("法院") or "")
    if not court:
        warns.append("empty_court")
    full = clean_text(row.get("全文") or "")
    if not full:
        errors.append("empty_full_text")
    elif len(full) < 50:
        warns.append("short_full_text")
    judgment_date = parse_date(row.get("裁判日期") or "")
    if (row.get("裁判日期") or "").strip() and not judgment_date:
        warns.append("invalid_judgment_date")
    basis = parse_basis(row.get("法律依据") or "")
    if not basis:
        warns.append("empty_legal_basis")
    if not (row.get("当事人") or "").strip():
        warns.append("empty_parties")

    clean = {
        "case_no": case_no,
        "title": title,
        "court": court,
        "region": clean_text(row.get("所属地区") or ""),
        "case_type": clean_text(row.get("案件类型") or ""),
        "procedure": clean_text(row.get("审理程序") or ""),
        "judgment_date": judgment_date,
        "judgment_date_raw": (row.get("裁判日期") or "").strip(),
        "cause": clean_text(row.get("案由") or "")[:100],
        "parties": clean_text(row.get("当事人") or ""),
        "basis": basis,
        "full": full,
        "source_member": row.get("_member", ""),
        "row_no": row.get("_row_no", 0),
    }
    clean["case_key"] = hid("K", case_no or title, court, judgment_date or "")
    clean["text_hash"] = hashlib.sha256(full.encode("utf-8")).hexdigest()
    clean["case_id"] = hid("CASE", clean["case_key"])
    return (None if errors else clean), errors, warns


def load_case(conn, c: dict) -> int:
    meta = {
        "court": c["court"], "region": c["region"], "case_type": c["case_type"],
        "procedure": c["procedure"], "judgment_date": c["judgment_date"],
        "cause": c["cause"],
    }
    store.add_node(conn, c["case_id"], "Case", c["title"] or c["case_no"],
                   c["source_member"], meta=meta)
    if c["court"]:
        court_id = hid("COURT", c["court"])
        store.add_node(conn, court_id, "Court", c["court"], meta={"region": c["region"]})
        store.add_edge(conn, c["case_id"], court_id, "HEARD_BY")
    chunks = 0
    text = c["full"]
    for i in range(0, len(text), 800):
        ch = hid("CH", c["case_id"], str(i))
        store.add_chunk(conn, ch, c["case_id"], text[i:i + 800])
        store.add_edge(conn, c["case_id"], ch, "CONTAINS")
        chunks += 1
    for b in c["basis"]:
        nid = hid("NORM", b["raw"])
        store.add_node(conn, nid, "Norm", b["raw"][:120], c["source_member"])
        store.add_edge(conn, c["case_id"], nid, "CITES", as_of=c["judgment_date"] or c["judgment_date_raw"] or None)
    return chunks


def _member_reader(z, member):
    raw = z.open(member)
    probe = raw.read(4096)
    enc = "utf-8-sig"
    for candidate in ("utf-8-sig", "gbk", "utf-8"):
        try:
            probe.decode(candidate)
            enc = candidate
            break
        except UnicodeDecodeError:
            continue
    raw.seek(0)
    return csv.DictReader(io.TextIOWrapper(raw, encoding=enc, newline=""))


def ingest_zip(conn, zip_path: str | Path, limit: int | None = None,
               dry_run: bool = False, db_path: str | Path | None = None, raw: bool = True) -> dict:
    zip_path = Path(zip_path)
    run_id = hid("RUN", str(zip_path), now())
    started = now()
    stats = {"run_id": run_id, "source": str(zip_path), "rows_read": 0, "rows_ok": 0,
             "rows_reject": 0, "duplicates": 0, "chunks": 0, "warns": 0,
             "members": 0, "errors": {}, "warns_by_type": {}, "reject_samples": []}
    if not dry_run:
        conn.execute(
            """INSERT INTO ingest_runs (id,source,started_at,status)
               VALUES (?,?,?,?)""", (run_id, str(zip_path), started, "running"))
        conn.commit()

    with zipfile.ZipFile(zip_path) as z:
        members = [n for n in z.namelist() if n.lower().endswith(".csv")]
        for member in members:
            stats["members"] += 1
            reader = _member_reader(z, member)
            if reader.fieldnames is None or not REQUIRED.issubset(set(reader.fieldnames)):
                stats["errors"]["bad_header"] = stats["errors"].get("bad_header", 0) + 1
                continue
            for row_no, row in enumerate(reader, 1):
                if limit and stats["rows_read"] >= limit:
                    break
                stats["rows_read"] += 1
                row["_member"] = member
                row["_row_no"] = row_no
                if not dry_run and raw:
                    raw_id = hid("RAW", run_id, member, str(row_no))
                    conn.execute(
                        """INSERT OR REPLACE INTO raw_rows
                           (id,run_id,source_member,row_no,raw_json,created_at)
                           VALUES (?,?,?,?,?,?)""",
                        (raw_id, run_id, member, row_no,
                         json.dumps(row, ensure_ascii=False)[:200000], now()))
                c, errors, warns = clean_row(row)
                for w in warns:
                    stats["warns"] += 1
                    stats["warns_by_type"][w] = stats["warns_by_type"].get(w, 0) + 1
                if errors:
                    stats["rows_reject"] += 1
                    for e in errors:
                        stats["errors"][e] = stats["errors"].get(e, 0) + 1
                    if len(stats["reject_samples"]) < 10:
                        stats["reject_samples"].append(
                            {"member": member, "row_no": row_no, "errors": errors,
                             "case_no": (row.get("案号") or "")[:50]})
                    if not dry_run:
                        rid = hid("REJ", run_id, member, str(row_no))
                        conn.execute(
                            """INSERT OR REPLACE INTO rejects
                               (id,run_id,source_member,row_no,reason,detail,raw_json,created_at)
                               VALUES (?,?,?,?,?,?,?,?)""",
                            (rid, run_id, member, row_no, ",".join(errors), "",
                             json.dumps(row, ensure_ascii=False)[:20000], now()))
                    continue
                if dry_run:
                    stats["rows_ok"] += 1
                    continue
                dup = conn.execute(
                    "SELECT id FROM dedup WHERE case_key=? OR text_hash=? LIMIT 1",
                    (c["case_key"], c["text_hash"])).fetchone()
                if dup:
                    stats["duplicates"] += 1
                    conn.execute(
                        """INSERT OR REPLACE INTO dedup
                           (id,run_id,case_key,text_hash,kept_case_id,reason,created_at)
                           VALUES (?,?,?,?,?,?,?)""",
                        (hid("DUP", run_id, c["case_key"]), run_id, c["case_key"],
                         c["text_hash"], dup["id"], "case_key_or_text_hash", now()))
                    continue
                chunks = load_case(conn, c)
                stats["chunks"] += chunks
                stats["rows_ok"] += 1
                for w in warns:
                    conn.execute(
                        "INSERT OR REPLACE INTO quality_flags (case_id,flag,detail) VALUES (?,?,?)",
                        (c["case_id"], w, ""))
                conn.execute(
                    """INSERT OR REPLACE INTO dedup
                       (id,run_id,case_key,text_hash,kept_case_id,reason,created_at)
                       VALUES (?,?,?,?,?,?,?)""",
                    (hid("DUP", run_id, c["case_key"]), run_id, c["case_key"],
                     c["text_hash"], c["case_id"], "inserted", now()))
                if stats["rows_read"] % 500 == 0:
                    conn.commit()
            if not dry_run:
                conn.execute(
                    """INSERT OR REPLACE INTO checkpoints (source,member,row_no,updated_at)
                       VALUES (?,?,?,?)""",
                    (str(zip_path), member, stats["rows_read"], now()))
                conn.commit()
            if limit and stats["rows_read"] >= limit:
                break

    stats["finished_at"] = now()
    if not dry_run:
        db_bytes = Path(db_path).stat().st_size if db_path and Path(db_path).exists() else 0
        stats["db_bytes"] = db_bytes
        stats["status"] = "done"
        conn.execute(
            """UPDATE ingest_runs SET finished_at=?, rows_read=?, rows_ok=?, rows_reject=?,
               duplicates=?, chunks=?, db_bytes=?, status=? WHERE id=?""",
            (stats["finished_at"], stats["rows_read"], stats["rows_ok"], stats["rows_reject"],
             stats["duplicates"], stats["chunks"], db_bytes, "done", run_id))
        conn.commit()
    return stats
