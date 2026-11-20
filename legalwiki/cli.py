"""CLI for legalwiki-kb MVP."""
from __future__ import annotations

import argparse
import json

from . import validity
from .graph import queries, store
from .ingest import claims as claim_extract
from .ingest import bulk_index, citations, titles
from .ingest import judgments
from .ingest import judgments_zip
from .ontology import loader as ontology
from .ingest import markdown
from .retrieval import embedder as embedder_mod
from .retrieval import hybrid as hybrid_mod
from .retrieval import vector_store


def ingest_demo(conn) -> None:
    store.add_node(conn, "LAW1", "Law", "示例法", "demo/law.md",
                   meta={"jurisdiction": "CN", "effective_date": "2020-01-01"})
    store.add_node(conn, "CH1", "Chapter", "第一章 总则", "demo/law.md")
    store.add_node(conn, "ART1", "Article", "第一条", "demo/law.md")
    store.add_edge(conn, "LAW1", "CH1", "CONTAINS")
    store.add_edge(conn, "CH1", "ART1", "CONTAINS")
    store.add_chunk(conn, "CK1", "ART1", "当事人应当依照本法履行义务。", 0, 20, "v1")
    store.add_edge(conn, "ART1", "CK1", "CONTAINS")
    conn.commit()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="legalwiki-kb")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init")
    p.add_argument("--db", required=True)

    p = sub.add_parser("ingest")
    p.add_argument("--db", required=True)
    p.add_argument("--docs")
    p.add_argument("--demo", action="store_true")

    p = sub.add_parser("ingest-judgments")
    p.add_argument("--db", required=True)
    p.add_argument("--path")
    p.add_argument("--zip")
    p.add_argument("--limit", type=int)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--no-raw", action="store_true")

    p = sub.add_parser("ontology")
    p.add_argument("--db", required=True)
    p.add_argument("--dir", default="ontology")

    p = sub.add_parser("index-judgments")
    p.add_argument("--db", required=True)
    p.add_argument("--zip", required=True)
    p.add_argument("--limit", type=int)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--no-fts", action="store_true")

    p = sub.add_parser("build-judgment-fts")
    p.add_argument("--db", required=True)
    p.add_argument("--full-text", action="store_true",
                   help="标题+全文一起索引（体积约 2.6 倍，构建小时级）")

    p = sub.add_parser("build-judgment-citations")
    p.add_argument("--db", required=True)
    p.add_argument("--limit", type=int)

    p = sub.add_parser("build-judgment-titles")
    p.add_argument("--db", required=True)

    p = sub.add_parser("check-citations")
    p.add_argument("--db", required=True)
    p.add_argument("--limit", type=int)

    p = sub.add_parser("extract")
    p.add_argument("--db", required=True)

    p = sub.add_parser("search")
    p.add_argument("--db", required=True)
    p.add_argument("--q", required=True)
    p.add_argument("--limit", type=int, default=5)

    p = sub.add_parser("evidence")
    p.add_argument("--db", required=True)
    p.add_argument("--claim", required=True)

    p = sub.add_parser("articles")
    p.add_argument("--db", required=True)
    p.add_argument("--law", required=True)

    p = sub.add_parser("embed-judgments")
    p.add_argument("--db", required=True)
    p.add_argument("--limit", type=int, default=5000)
    p.add_argument("--backend", choices=["fake", "qwen", "local"], default="fake")
    p.add_argument("--model", default=None)
    p.add_argument("--dim", type=int, default=64, help="fake 向量维度")
    p.add_argument("--batch-size", type=int, default=64)
    p.add_argument("--max-chars", type=int, default=1000)

    p = sub.add_parser("search-hybrid")
    p.add_argument("--db", required=True)
    p.add_argument("--q", required=True)
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--backend", choices=["fake", "qwen", "local"], default="fake")
    p.add_argument("--model", default=None)
    p.add_argument("--dim", type=int, default=64)
    p.add_argument("--fts-limit", type=int, default=50)
    p.add_argument("--vector-limit", type=int, default=50)

    args = parser.parse_args(argv)
    if args.cmd == "init":
        store.init_db(args.db)
        print(f"initialized {args.db}")
        return 0
    if args.cmd == "ingest":
        conn = store.init_db(args.db)
        if args.demo:
            ingest_demo(conn)
            print("demo ingested")
        elif args.docs:
            stats = markdown.ingest_dir(conn, args.docs)
            print(f"ingested {len(stats)} files")
            for s in stats[:10]:
                print(f"  {s['law']} sections={s['sections']} chunks={s['chunks']}")
        else:
            print("use --demo or --docs")
        return 0
    if args.cmd == "index-judgments":
        conn = store.init_db(args.db)
        stats = bulk_index.index_zip(conn, args.zip, limit=args.limit, dry_run=args.dry_run, build_fts_index=not args.no_fts)
        print(json.dumps(stats, ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "build-judgment-fts":
        conn = store.init_db(args.db)
        print(f"fts={bulk_index.build_fts(conn, full_text=args.full_text)}")
        return 0
    if args.cmd == "ingest-judgments":
        conn = store.init_db(args.db)
        if args.zip:
            s = judgments_zip.ingest_zip(conn, args.zip, limit=args.limit,
                                         dry_run=args.dry_run, db_path=args.db, raw=not args.no_raw)
            print(json.dumps(s, ensure_ascii=False, indent=2))
            return 0
        if args.path:
            stats = judgments.ingest_dir(conn, args.path)
            print(f"files={len(stats)} cases={sum(s['cases'] for s in stats)} chunks={sum(s['chunks'] for s in stats)} norms={sum(s['norms'] for s in stats)}")
            return 0
        print("use --zip or --path")
        return 2
    if args.cmd == "ontology":
        conn = store.init_db(args.db)
        stats = ontology.load(conn, args.dir)
        print(f"concepts={stats['concepts']} rules={stats['rules']} articles={stats['articles']}")
        return 0
    if args.cmd == "build-judgment-citations":
        conn = store.init_db(args.db)
        print(json.dumps(citations.build_citations(conn, args.limit), ensure_ascii=False))
        return 0
    if args.cmd == "build-judgment-titles":
        conn = store.init_db(args.db)
        print(f"titles={titles.build_titles(conn)}")
        return 0
    if args.cmd == "check-citations":
        conn = store.init_db(args.db)
        print(json.dumps(validity.check_citations(conn, args.limit), ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "extract":
        conn = store.init_db(args.db)
        stats = claim_extract.extract_all(conn)
        print(f"chunks={stats['chunks']} claims={stats['claims']}")
        return 0
    if args.cmd == "search":
        conn = store.init_db(args.db)
        for row in queries.search_chunks(conn, args.q, args.limit):
            print(f"{row['chunk_id']}\t{row['text'][:80]}")
        return 0
    if args.cmd == "evidence":
        conn = store.init_db(args.db)
        for row in queries.evidence_chain(conn, args.claim):
            print(f"{row['id']}\t{row['role']}\t{row['kind']}\t{row['ref']}")
        return 0
    if args.cmd == "articles":
        conn = store.init_db(args.db)
        for row in queries.articles_of(conn, args.law):
            print(f"{row['id']}\t{row['type']}")
        return 0
    if args.cmd == "embed-judgments":
        conn = store.init_db(args.db)
        if args.backend == "qwen":
            emb = embedder_mod.make_embedder("qwen", model=args.model or "text-embedding-v3")
        elif args.backend == "local":
            emb = embedder_mod.make_embedder("local")
        else:
            emb = embedder_mod.make_embedder("fake", dim=args.dim)
        stats = vector_store.embed_judgments(
            conn, emb, limit=args.limit, model=args.model, batch_size=args.batch_size,
            max_chars=args.max_chars, backend=args.backend)
        print(json.dumps(stats, ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "search-hybrid":
        conn = store.init_db(args.db)
        vector_store.ensure_schema(conn)
        if args.backend == "qwen":
            emb = embedder_mod.make_embedder("qwen", model=args.model or "text-embedding-v3")
        elif args.backend == "local":
            emb = embedder_mod.make_embedder("local")
        else:
            emb = embedder_mod.make_embedder("fake", dim=args.dim)
        rows = hybrid_mod.search_hybrid(
            conn, args.q, emb, limit=args.limit, model=args.model,
            fts_limit=args.fts_limit, vector_limit=args.vector_limit)
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
