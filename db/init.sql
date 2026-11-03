CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS documents (
  id              TEXT PRIMARY KEY,
  doc_type        TEXT NOT NULL CHECK (doc_type IN ('spec','drawing','submittal','addendum')),
  title           TEXT,
  source_url      TEXT,
  section_code    TEXT,          -- MasterFormat, e.g. '09 91 00'
  sheet_number    TEXT,          -- e.g. 'A-301'
  revision        TEXT NOT NULL, -- e.g. 'UFGS-2026-08' or 'Addendum 2'
  effective_date  DATE,
  supersedes_id   TEXT REFERENCES documents(id),
  sha256          TEXT NOT NULL
);

-- Embedding dimension must match the embedding model; 1024 = voyage-3.5.
CREATE TABLE IF NOT EXISTS chunks (
  id            TEXT PRIMARY KEY,
  document_id   TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  section_path  TEXT,
  page          INT,
  text          TEXT NOT NULL,
  embedding     vector(1024),
  tsv           tsvector GENERATED ALWAYS AS (to_tsvector('english', text)) STORED
);

CREATE INDEX IF NOT EXISTS chunks_tsv_idx ON chunks USING GIN (tsv);
CREATE INDEX IF NOT EXISTS chunks_embedding_idx ON chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS documents_section_idx ON documents (section_code, revision);

-- Fixed-size chunking of the same corpus, for baseline B1 and the
-- -section-chunking ablation. Same shape as chunks.
CREATE TABLE IF NOT EXISTS chunks_fixed (
  id            TEXT PRIMARY KEY,
  document_id   TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  section_path  TEXT,
  page          INT,
  text          TEXT NOT NULL,
  embedding     vector(1024),
  tsv           tsvector GENERATED ALWAYS AS (to_tsvector('english', text)) STORED
);

CREATE INDEX IF NOT EXISTS chunks_fixed_tsv_idx ON chunks_fixed USING GIN (tsv);
CREATE INDEX IF NOT EXISTS chunks_fixed_embedding_idx ON chunks_fixed USING hnsw (embedding vector_cosine_ops);

-- Per-request pipeline telemetry (one row per POST /rfi, best-effort writes).
CREATE TABLE IF NOT EXISTS rfi_requests (
  id               TEXT PRIMARY KEY,
  question_sha256  TEXT NOT NULL,
  rfi_type         TEXT,
  verdict          TEXT NOT NULL CHECK (verdict IN ('answered','gap')),
  total_latency_ms INT NOT NULL,
  total_cost_usd   NUMERIC(10,6) NOT NULL,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS rfi_request_stages (
  request_id    TEXT NOT NULL REFERENCES rfi_requests(id) ON DELETE CASCADE,
  stage         TEXT NOT NULL,
  latency_ms    INT NOT NULL,
  input_tokens  INT NOT NULL,
  output_tokens INT NOT NULL,
  cost_usd      NUMERIC(10,6) NOT NULL,
  model         TEXT,
  PRIMARY KEY (request_id, stage)
);
