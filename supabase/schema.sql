-- ============================================================
-- Supabase PostgreSQL + pgvector Schema for README RAG Chatbot
-- ============================================================

-- 1. Enable Required Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Projects Table
-- Stores metadata, repo identification, SHA-256 hash of README, and embedding configurations.
CREATE TABLE IF NOT EXISTS projects (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    github_url TEXT UNIQUE NOT NULL,
    owner TEXT NOT NULL,
    repo_name TEXT NOT NULL,
    readme_hash TEXT,
    readme_url TEXT,
    embedding_model TEXT NOT NULL DEFAULT 'sentence-transformers/all-MiniLM-L6-v2',
    embedding_dimension INTEGER NOT NULL DEFAULT 384,
    indexed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Readme Chunks Table
-- Stores section-aware chunked content and high-dimensional vector embeddings.
-- Note: Default embedding dimension is 384 for sentence-transformers/all-MiniLM-L6-v2.
-- If using BAAI/bge-base-en-v1.5 (768), modify the vector dimension accordingly:
-- e.g., ALTER TABLE readme_chunks ALTER COLUMN embedding TYPE VECTOR(768);
CREATE TABLE IF NOT EXISTS readme_chunks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    section_title TEXT,
    section_path TEXT,
    content TEXT NOT NULL,
    embedding VECTOR(384),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. Performance Indexes
-- B-Tree Index for fast project-isolated chunk lookups and cascading operations
CREATE INDEX IF NOT EXISTS idx_readme_chunks_project_id ON readme_chunks (project_id);
CREATE INDEX IF NOT EXISTS idx_projects_github_url ON projects (github_url);

-- Vector Index (HNSW for high recall and fast approximate nearest neighbors search)
CREATE INDEX IF NOT EXISTS idx_readme_chunks_embedding_hnsw 
ON readme_chunks 
USING hnsw (embedding vector_cosine_ops);

-- 5. Row Level Security (RLS) Configuration
-- Enable RLS to secure tables from unauthorized public writes
ALTER TABLE projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE readme_chunks ENABLE ROW LEVEL SECURITY;

-- Allow public read/search access (writes are reserved for service_role key)
DROP POLICY IF EXISTS "Allow public read on projects" ON projects;
CREATE POLICY "Allow public read on projects" ON projects FOR SELECT USING (true);

DROP POLICY IF EXISTS "Allow public read on readme_chunks" ON readme_chunks;
CREATE POLICY "Allow public read on readme_chunks" ON readme_chunks FOR SELECT USING (true);

-- 5. Vector Search RPC Function (Isolated by project_id)
-- Executes cosine similarity search strictly within the specified project's chunks.
CREATE OR REPLACE FUNCTION match_readme_chunks (
    query_embedding VECTOR,
    match_project_id UUID,
    match_count INT DEFAULT 5,
    similarity_threshold FLOAT DEFAULT 0.0
)
RETURNS TABLE (
    id UUID,
    project_id UUID,
    chunk_index INT,
    section_title TEXT,
    section_path TEXT,
    content TEXT,
    similarity FLOAT
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    RETURN QUERY
    SELECT
        rc.id,
        rc.project_id,
        rc.chunk_index,
        rc.section_title,
        rc.section_path,
        rc.content,
        (1 - (rc.embedding <=> query_embedding))::FLOAT AS similarity
    FROM readme_chunks rc
    WHERE rc.project_id = match_project_id
      AND (1 - (rc.embedding <=> query_embedding)) >= similarity_threshold
    ORDER BY rc.embedding <=> query_embedding ASC
    LIMIT match_count;
END;
$$;
