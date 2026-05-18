-- stt_analysis 스키마 초기 생성
-- 실행: psql -h localhost -p 54322 -U postgres -d postgres -f migrations/init_schema.sql

CREATE SCHEMA IF NOT EXISTS stt_analysis;

CREATE TABLE IF NOT EXISTS stt_analysis.collections (
    id TEXT PRIMARY KEY,
    type TEXT,
    name TEXT,
    source_url TEXT,
    channel TEXT,
    item_count INTEGER DEFAULT 0,
    total_duration FLOAT DEFAULT 0,
    total_chars INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending',
    progress INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS stt_analysis.videos (
    id TEXT PRIMARY KEY,
    title TEXT,
    source TEXT DEFAULT 'youtube',
    channel TEXT,
    url TEXT,
    duration_sec INTEGER DEFAULT 0,
    text_length INTEGER DEFAULT 0,
    segment_count INTEGER DEFAULT 0,
    language TEXT DEFAULT 'ko',
    collection_id TEXT REFERENCES stt_analysis.collections(id) ON DELETE SET NULL,
    thumbnail TEXT,
    preview TEXT,
    upload_date DATE,
    processed_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS stt_analysis.transcripts (
    video_id TEXT PRIMARY KEY REFERENCES stt_analysis.videos(id) ON DELETE CASCADE,
    full_text TEXT,
    corrected_text TEXT,
    stt_source TEXT,
    correction_model TEXT,
    segments JSONB,
    ocr_text TEXT,
    ocr_frames_total INTEGER DEFAULT 0,
    ocr_frames_unique INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS stt_analysis.ai_tasks (
    id TEXT PRIMARY KEY,
    video_ids JSONB NOT NULL,
    video_titles JSONB DEFAULT '{}',
    prompt TEXT NOT NULL,
    output_type TEXT DEFAULT 'text',
    model TEXT DEFAULT 'sonnet',
    status TEXT DEFAULT 'pending',
    parent_task_id TEXT,
    result_text TEXT,
    error_msg TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS stt_analysis.shares (
    token TEXT PRIMARY KEY,
    video_id TEXT REFERENCES stt_analysis.videos(id) ON DELETE CASCADE,
    view_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS stt_analysis.user_quota (
    user_id TEXT PRIMARY KEY,
    quota_type TEXT NOT NULL DEFAULT 'free',
    daily_used INTEGER NOT NULL DEFAULT 0,
    last_reset_date DATE NOT NULL DEFAULT CURRENT_DATE,
    total_used INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS stt_analysis.qa_history (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    video_id TEXT NOT NULL,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    model TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_videos_channel ON stt_analysis.videos(channel);
CREATE INDEX IF NOT EXISTS idx_videos_collection ON stt_analysis.videos(collection_id);
CREATE INDEX IF NOT EXISTS idx_videos_upload_date ON stt_analysis.videos(upload_date DESC);
CREATE INDEX IF NOT EXISTS idx_qa_history_user_video ON stt_analysis.qa_history(user_id, video_id);
CREATE INDEX IF NOT EXISTS idx_qa_history_video ON stt_analysis.qa_history(video_id);
CREATE INDEX IF NOT EXISTS idx_user_quota_type ON stt_analysis.user_quota(quota_type);
