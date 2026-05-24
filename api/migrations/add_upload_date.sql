-- YouTube 업로드 날짜 컬럼 추가
-- 실행: psql -h localhost -p 54322 -U postgres -d postgres -f migrations/add_upload_date.sql

ALTER TABLE stt_analysis.videos
    ADD COLUMN IF NOT EXISTS upload_date DATE;
