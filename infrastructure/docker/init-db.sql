-- Runs automatically on first Postgres container init (mounted into
-- /docker-entrypoint-initdb.d). Enables the pgvector extension used by
-- `tender_embeddings` for semantic search (Sprint 7). Safe to run even
-- though no vector columns exist yet in Sprint 1.
CREATE EXTENSION IF NOT EXISTS vector;
