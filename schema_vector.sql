-- migration: vector prototype tables (existing legalwiki DBs)
CREATE TABLE IF NOT EXISTS judgment_embeddings (
  judgment_id TEXT NOT NULL,
  model TEXT NOT NULL,
  dim INTEGER NOT NULL,
  vector BLOB NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (judgment_id, model)
);
CREATE INDEX IF NOT EXISTS idx_judgment_embeddings_model
  ON judgment_embeddings(model);
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
