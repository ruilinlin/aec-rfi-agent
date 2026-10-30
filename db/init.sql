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

-- Embedding dimension must match the embedding model; 1536 is a placeholder.
CREATE TABLE IF NOT EXISTS chunks (
  id            TEXT PRIMARY KEY,
  document_id   TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  section_path  TEXT,
  page          INT,
  text          TEXT NOT NULL,
  embedding     vector(1536),
  tsv           tsvector GENERATED ALWAYS AS (to_tsvector('english', text)) STORED
);

CREATE INDEX IF NOT EXISTS chunks_tsv_idx ON chunks USING GIN (tsv);
CREATE INDEX IF NOT EXISTS chunks_embedding_idx ON chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS documents_section_idx ON documents (section_code, revision);
