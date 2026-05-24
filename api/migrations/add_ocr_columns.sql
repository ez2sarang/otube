-- OCR 결과 저장 컬럼 추가
-- 실행: psql -h localhost -p 54322 -U postgres -d postgres -f migrations/add_ocr_columns.sql

ALTER TABLE stt_analysis.transcripts
    ADD COLUMN IF NOT EXISTS ocr_text TEXT,
    ADD COLUMN IF NOT EXISTS ocr_frames_total INT DEFAULT 0,
    ADD COLUMN IF NOT EXISTS ocr_frames_unique INT DEFAULT 0;
