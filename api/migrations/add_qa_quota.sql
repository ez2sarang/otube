-- Q&A 및 쿼터 관리 테이블 생성

-- 사용 쿼터 테이블
CREATE TABLE IF NOT EXISTS stt_analysis.user_quota (
    user_id TEXT NOT NULL,
    quota_type TEXT NOT NULL DEFAULT 'free',  -- 'free' | 'premium'
    daily_used INTEGER NOT NULL DEFAULT 0,
    last_reset_date DATE NOT NULL DEFAULT CURRENT_DATE,
    total_used INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id)
);

-- Q&A 히스토리 테이블
CREATE TABLE IF NOT EXISTS stt_analysis.qa_history (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    video_id TEXT NOT NULL,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    model TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 인덱스 생성
CREATE INDEX IF NOT EXISTS idx_qa_history_user_video
    ON stt_analysis.qa_history(user_id, video_id);

CREATE INDEX IF NOT EXISTS idx_qa_history_video
    ON stt_analysis.qa_history(video_id);

CREATE INDEX IF NOT EXISTS idx_user_quota_type
    ON stt_analysis.user_quota(quota_type);
