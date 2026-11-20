-- legalwiki-kb schema v0.1
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS nodes (
  id TEXT PRIMARY KEY,
  type TEXT NOT NULL,          -- Law/Chapter/Article/Case/Court/Norm/Claim/Evidence
  label TEXT,
  source_path TEXT,
  span_start INTEGER,
  span_end INTEGER,
  version TEXT,
  hash TEXT,
  meta TEXT,                   -- JSON: jurisdiction/effective_date/expiry_date
  effective_from TEXT,
  effective_to TEXT,
  status TEXT,
  created_at TEXT
);

CREATE TABLE IF NOT EXISTS edges (
  id TEXT PRIMARY KEY,
  src TEXT NOT NULL,
  dst TEXT NOT NULL,
  type TEXT NOT NULL,          -- CONTAINS/CITES/APPLIES_TO/AMENDS/SUPERSEDES/CONTRADICTS/SUPPORTS/DERIVED_FROM
  source_span TEXT,
  version TEXT,
  confidence REAL,
  as_of TEXT,
  created_at TEXT
);

CREATE TABLE IF NOT EXISTS evidence (
  id TEXT PRIMARY KEY,
  claim_id TEXT NOT NULL,
  role TEXT NOT NULL,          -- norm/fact
  kind TEXT NOT NULL,          -- law/regulation/contract/judgment/document
  ref TEXT NOT NULL,
  span TEXT,
  valid INTEGER DEFAULT 1,
  created_at TEXT
);

CREATE TABLE IF NOT EXISTS versions (
  id TEXT PRIMARY KEY,
  node_id TEXT NOT NULL,
  old_hash TEXT,
  new_hash TEXT,
  reason TEXT,
  created_at TEXT
);

CREATE TABLE IF NOT EXISTS chunks (
  id TEXT PRIMARY KEY,
  node_id TEXT NOT NULL,
  text TEXT NOT NULL,
  span_start INTEGER,
  span_end INTEGER,
  version TEXT,
  hash TEXT,
  token_count INTEGER
);

CREATE INDEX IF NOT EXISTS idx_edges_src ON edges(src, type);
CREATE INDEX IF NOT EXISTS idx_edges_dst ON edges(dst, type);
CREATE INDEX IF NOT EXISTS idx_evidence_claim ON evidence(claim_id);

CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
  chunk_id UNINDEXED,
  text,
  tokenize='trigram'
);

CREATE TABLE IF NOT EXISTS ingest_runs (
  id TEXT PRIMARY KEY, source TEXT, started_at TEXT, finished_at TEXT,
  rows_read INTEGER, rows_ok INTEGER, rows_reject INTEGER,
  duplicates INTEGER, chunks INTEGER, db_bytes INTEGER, status TEXT
);

CREATE TABLE IF NOT EXISTS raw_rows (
  id TEXT PRIMARY KEY, run_id TEXT, source_member TEXT, row_no INTEGER,
  raw_json TEXT, created_at TEXT
);

CREATE TABLE IF NOT EXISTS rejects (
  id TEXT PRIMARY KEY, run_id TEXT, source_member TEXT, row_no INTEGER,
  reason TEXT, detail TEXT, raw_json TEXT, created_at TEXT
);

CREATE TABLE IF NOT EXISTS dedup (
  id TEXT PRIMARY KEY, run_id TEXT, case_key TEXT, text_hash TEXT,
  kept_case_id TEXT, reason TEXT, created_at TEXT
);

CREATE TABLE IF NOT EXISTS quality_flags (
  case_id TEXT, flag TEXT, detail TEXT, PRIMARY KEY (case_id, flag)
);

CREATE TABLE IF NOT EXISTS checkpoints (
  source TEXT PRIMARY KEY, member TEXT, row_no INTEGER, updated_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_rejects_run ON rejects(run_id);
CREATE INDEX IF NOT EXISTS idx_dedup_key ON dedup(case_key);
CREATE INDEX IF NOT EXISTS idx_dedup_hash ON dedup(text_hash);

CREATE UNIQUE INDEX IF NOT EXISTS uq_edges ON edges(src,dst,type);


CREATE TABLE IF NOT EXISTS judgments (
  id TEXT PRIMARY KEY,
  case_no TEXT, title TEXT, court TEXT, region TEXT,
  case_type TEXT, procedure TEXT, judgment_date TEXT,
  cause TEXT, basis TEXT, full_text TEXT, text_hash TEXT,
  source_member TEXT, row_no INTEGER
);
CREATE INDEX IF NOT EXISTS idx_judgments_court ON judgments(court);
CREATE INDEX IF NOT EXISTS idx_judgments_date ON judgments(judgment_date);
CREATE VIRTUAL TABLE IF NOT EXISTS judgments_fts USING fts5(
  judgment_id UNINDEXED,
  title,
  full_text,
  tokenize='trigram'
);

-- vector prototype (task-84): title + first 1000 chars embedded
CREATE TABLE IF NOT EXISTS judgment_embeddings (
  judgment_id TEXT NOT NULL,
  model TEXT NOT NULL,
  dim INTEGER NOT NULL,
  vector BLOB NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (judgment_id, model)
);
CREATE INDEX IF NOT EXISTS idx_judgment_embeddings_model ON judgment_embeddings(model);

CREATE TABLE IF NOT EXISTS embedding_runs (
  id TEXT PRIMARY KEY,
  model TEXT NOT NULL,
  dim INTEGER NOT NULL,
  backend TEXT NOT NULL,
  rows_embedded INTEGER NOT NULL,
  started_at TEXT NOT NULL,
  finished_at TEXT NOT NULL,
  status TEXT NOT NULL,
  detail TEXT
);



CREATE TABLE IF NOT EXISTS judgment_citations (
  judgment_id TEXT NOT NULL,
  law TEXT,
  article TEXT,
  raw TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_citations_law ON judgment_citations(law);
CREATE INDEX IF NOT EXISTS idx_citations_judgment ON judgment_citations(judgment_id);


CREATE TABLE IF NOT EXISTS judgment_titles (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL
);
