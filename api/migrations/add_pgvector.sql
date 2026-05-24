-- pgvector 확장 + 임베딩 열 추가
CREATE EXTENSION IF NOT EXISTS vector;

-- transcripts 테이블에 임베딩 열 추가
ALTER TABLE stt_analysis.transcripts
  ADD COLUMN IF NOT EXISTS embedding vector(384),
  ADD COLUMN IF NOT EXISTS embedded_at TIMESTAMPTZ;

-- 임베딩 인덱스 생성 (cosine similarity for semantic search)
CREATE INDEX IF NOT EXISTS idx_transcripts_embedding
  ON stt_analysis.transcripts
  USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 100);
