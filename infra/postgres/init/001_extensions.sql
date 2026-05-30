-- Runs automatically on first database initialization (empty data volume).
-- Enables the pgvector extension used for storing chunk embeddings.

CREATE EXTENSION IF NOT EXISTS vector;
