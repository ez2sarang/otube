# otube — YouTube 영상 AI 분석 플랫폼

> YouTube 영상을 URL 하나로 자막 추출, AI 교정, 슬라이드 캡처, LLM Q&A까지 자동화하는 SaaS 파이프라인.

**문의:** sales@com.dooray.com

---

## 목차

1. [서비스 개요](#서비스-개요)
2. [아키텍처](#아키텍처)
3. [분석 파이프라인 상세](#분석-파이프라인-상세)
4. [기술 스택](#기술-스택)
5. [DB 스키마](#db-스키마)
6. [API 레퍼런스](#api-레퍼런스)
7. [로컬 개발 환경 설정](#로컬-개발-환경-설정)
8. [프로덕션 배포](#프로덕션-배포)
9. [환경변수](#환경변수)
10. [프로젝트 구조](#프로젝트-구조)
11. [유료화 모델](#유료화-모델)

---

## 서비스 개요

otube는 긴 YouTube 영상을 분석·문서화·2차 AI 가공이 필요한 모든 사람을 위한 오프라인 AI 분석 도구다.

**핵심 기능:**

| 기능 | 설명 |
|------|------|
| 자막 추출 | VTT 자동자막 우선 수집, 없으면 mlx-whisper STT 폴백 |
| AI 교정 | claude-haiku 기반 STT 오류 자동 교정 |
| 슬라이드 캡처 | ffmpeg 장면 감지 + OCR로 핵심 프레임 자동 추출 |
| LLM Q&A | 저장된 트랜스크립트 기반 실시간 질의응답 |
| 컬렉션 관리 | 채널 또는 재생목록 단위로 영상 일괄 수집 |
| 전문 검색 | OCR 텍스트 전문(Full-text) 슬라이드 검색 |
| AI 분석 작업 | 트랜스크립트 기반 요약·번역·분석 자동화 |

**지원 언어:** 한국어 (ko) / 영어 (en) — 자막 수집 및 LLM 응답 모두 지원

---

## 아키텍처

```
┌─────────────────────────────────────────────────────────────────────┐
│  브라우저 (사용자)                                                       │
│  Next.js 16 프론트엔드 — localhost:3204                                │
└────────────────────────┬────────────────────────────────────────────┘
                         │ HTTP / SSE
┌────────────────────────▼────────────────────────────────────────────┐
│  FastAPI 백엔드 — localhost:9102                                      │
│                                                                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐│
│  │ /stt     │  │ /slides  │  │ /qa      │  │ /ai-tasks            ││
│  │ /tasks   │  │ /search  │  │ /quota   │  │ /collections         ││
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └──────────────────────┘│
│       │              │              │                                  │
│  ┌────▼──────────────▼──────────────▼──────────────────────────────┐│
│  │  TaskManager (동시처리 세마포어, SSE 스트리밍)                     ││
│  └───────────────────────────────────────────────────────────────── ┘│
└──────────────┬─────────────────┬──────────────────────────────────── ┘
               │                 │
    ┌──────────▼──────┐  ┌───────▼──────────────────────────────────┐
    │  PostgreSQL DB   │  │  외부 도구                                │
    │  (stt_analysis)  │  │  yt-dlp | ffmpeg | mlx-whisper           │
    │  localhost:54322 │  │  pytesseract | claude CLI                │
    └──────────────────┘  └──────────────────────────────────────────┘
                                    │
                          ┌─────────▼────────────────────┐
                          │  LLM 게이트웨이               │
                          │  localhost:3100/PIN/llm-gateway│
                          └──────────────────────────────┘
```

---

## 분석 파이프라인 상세

YouTube URL 하나를 입력하면 아래 파이프라인이 순차적으로 실행된다.

```
POST /api/transcribe/youtube
        │
        ▼
1. yt-dlp 메타데이터 수집
   ─ 영상 제목, 채널, 길이, 업로드 날짜
   ─ Chrome 쿠키 자동 적용 (인증 영상 지원)
        │
        ▼
2. VTT 자막 다운로드 시도 (언어 코드 지정)
   ─ 성공 → Step 3 (LLM 교정)
   ─ 실패 → Step 4 (Whisper STT)
        │
        ├─── [VTT 있음] ────────────────────────────────────────────┐
        │                                                            │
        ▼                                                            │
3. LLM 교정 (claude-haiku via llm-gateway)                          │
   ─ VTT 중복 라인·타임스탬프 파싱 → 정제된 plain text               │
   ─ 받아쓰기 오류·전문용어 교정 → corrected_text                     │
   ─ stt_source = 'vtt_llm'                                         │
        │                                                            │
        ├─── [VTT 없음] ─────────────────────────────────────────── ┘
        ▼
4. Whisper STT 폴백
   ─ yt-dlp로 오디오 스트림 다운로드 → /tmp/stt-work/{vid_id}/
   ─ mlx-whisper (Apple Silicon) / faster-whisper (cloud) 실행
   ─ 세그먼트 타임스탬프 포함 텍스트 생성
   ─ stt_source = 'whisper'
        │
        ▼ (STT 완료 후 병렬 실행)
5. 슬라이드 추출 (ffmpeg 장면 감지)
   ─ yt-dlp로 영상 다운로드
   ─ ffmpeg scene detection → 키프레임 추출
   ─ pytesseract OCR → 프레임별 텍스트 추출
   ─ OCR 유사도 0.85 이상 중복 프레임 제거
   ─ 이미지 BYTEA로 stt_analysis.slides DB 저장
        │
        ▼
6. PostgreSQL 저장
   ─ stt_analysis.videos: 영상 메타데이터
   ─ stt_analysis.transcripts: 원본·교정 텍스트, 세그먼트, OCR
   ─ stt_analysis.slides: 슬라이드 이미지(BYTEA) + OCR 텍스트
        │
        ▼
7. LLM Q&A 제공 (POST /api/qa/{video_id})
   ─ transcripts.corrected_text를 컨텍스트로 LLM 호출
   ─ 무료: 일 10회 / premium: 무제한
   ─ qa_history 테이블에 히스토리 기록
```

### LLM 게이트웨이 통신 방식

LLM 호출은 paperCompany 내부 게이트웨이를 통해 비동기 콜백 방식으로 처리된다.

```
FastAPI → POST localhost:3100/api/plugins/llm-gateway/webhooks/process
              (request_id, model, prompt 전송)
              ↓
          LLM 처리 완료 시 콜백
              ↓
FastAPI ← POST /internal/llm-callback/{request_id}
              (결과 수신 후 threading.Event 해제)
```

게이트웨이 불가 시 `claude CLI --print` 모드로 직접 폴백한다.

---

## 기술 스택

### 백엔드

| 컴포넌트 | 기술 | 버전 |
|---------|------|------|
| 웹 프레임워크 | FastAPI | 0.128.8 |
| ASGI 서버 | uvicorn + uvloop | 0.39.0 |
| DB 드라이버 | psycopg2-binary | 2.9.12 |
| STT (Apple Silicon) | mlx-whisper | 0.4.2 |
| 이미지 처리 | Pillow | 10.4.0 |
| 자막 다운로드 | yt-dlp | 최신 |
| 비디오 처리 | ffmpeg | 시스템 설치 |
| OCR | pytesseract | 시스템 설치 |
| 런타임 | Python | 3.10+ |

### 프론트엔드

| 컴포넌트 | 기술 | 버전 |
|---------|------|------|
| 프레임워크 | Next.js | 16.2.1 |
| UI 라이브러리 | React | 19.2.4 |
| 스타일링 | Tailwind CSS | 4.x |
| 컴포넌트 | shadcn/ui | 4.x |
| Markdown 렌더러 | react-markdown + remark-gfm | 10.x |
| 언어 | TypeScript | 5.x |

### 인프라

| 컴포넌트 | 기술 | 비고 |
|---------|------|------|
| DB | PostgreSQL 16 | Supabase 로컬 (port 54322) 또는 Docker (port 54399) |
| LLM | claude-haiku / sonnet / opus | paperCompany 내부 게이트웨이 경유 |
| 유료화 (예정) | Stripe | stripe_payments.py 스켈레톤 구현 완료 |
| 인증 (예정) | Supabase Auth / JWT | auth.py 스켈레톤, 현재는 X-User-Id 헤더 |

---

## DB 스키마

스키마명: `stt_analysis` (레거시 이름. 신규 테이블은 `offline_thinking` 스키마를 사용할 것)

### 테이블 구조

| 테이블 | 설명 | 주요 컬럼 |
|--------|------|----------|
| `videos` | 영상 메타데이터 | id (YouTube vid), title, channel, url, duration_sec, upload_date, thumbnail |
| `transcripts` | STT/VTT 결과 | video_id (FK), full_text, corrected_text, stt_source, segments (JSONB), ocr_text |
| `slides` | 슬라이드 프레임 | video_id, slide_index, image_data (BYTEA), ocr_text, frame_time, time_str |
| `collections` | 채널/재생목록 수집 그룹 | id, type, name, source_url, channel, item_count, status, progress |
| `ai_tasks` | AI 분석 작업 이력 | id, video_ids (JSONB), prompt, model, status, result_text, parent_task_id |
| `user_quota` | 사용 쿼터 관리 | user_id, quota_type (free/premium), daily_used, last_reset_date, total_used |
| `qa_history` | Q&A 히스토리 | user_id, video_id, question, answer, model, created_at |
| `shares` | 공유 링크 토큰 | token, video_id, view_count |

### 주요 인덱스

```sql
idx_videos_channel           ON videos(channel)
idx_videos_collection        ON videos(collection_id)
idx_videos_upload_date       ON videos(upload_date DESC)
idx_qa_history_user_video    ON qa_history(user_id, video_id)
idx_qa_history_video         ON qa_history(video_id)
idx_user_quota_type          ON user_quota(quota_type)
```

### transcripts.stt_source 값

| 값 | 의미 |
|----|------|
| `vtt_llm` | YouTube VTT 자막 → LLM 교정 |
| `whisper` | mlx-whisper 또는 faster-whisper STT |

---

## API 레퍼런스

베이스 URL: `http://localhost:9102`  
OpenAPI 문서: `http://localhost:9102/docs`

### STT / 트랜스크립션

#### `POST /api/transcribe/youtube`
YouTube URL 분석 시작. 비동기 처리 — task_id로 상태를 폴링한다.

**Request Body:**
```json
{
  "url": "https://www.youtube.com/watch?v=VIDEO_ID",
  "language": "ko"
}
```

**Response:**
```json
{ "task_id": "abc123" }
```

---

#### `POST /api/transcribe/file`
로컬 오디오/영상 파일 업로드 후 Whisper STT 실행.

**Form Data:**
| 필드 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `file` | File | — | 오디오/영상 파일 |
| `language` | string | `"ko"` | 인식 언어 |
| `model` | string | `"mlx-community/whisper-large-v3-turbo"` | Whisper 모델 |

**Response:**
```json
{ "task_id": "xyz789" }
```

---

### 태스크 / 실시간 진행

#### `GET /api/tasks/{task_id}`
작업 현재 상태 조회.

**Response:**
```json
{
  "task_id": "abc123",
  "status": "running",
  "message": "자막 보정 + OCR 프레임 분석 중...",
  "progress": 40,
  "result": null,
  "error": null
}
```

`status` 값: `pending` | `running` | `done` | `error`

---

#### `GET /api/tasks/{task_id}/events`
SSE(Server-Sent Events)로 실시간 진행률 스트리밍.

**Media-Type:** `text/event-stream`

**Event 형식:**
```
data: {"status":"running","message":"슬라이드 추출 중...","progress":93}

data: {"status":"done","message":"완료","progress":100,"result":{...}}
```

---

### 영상 목록 / 상세

#### `GET /api/videos`
분석 완료된 영상 목록 조회. (routers/collections.py 참고)

#### `GET /api/videos/{id}`
영상 상세 정보 + 트랜스크립트 세그먼트.

---

### 슬라이드

#### `GET /api/slides`
모든 영상의 슬라이드 요약 목록 (영상별 슬라이드 수 포함).

**Response:**
```json
[
  {
    "vid_id": "dQw4w9WgXcQ",
    "title": "영상 제목",
    "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "total_slides": 42,
    "extracted_at": "2026-06-05T10:00:00+00:00",
    "thumbnail": "/api/slides/dQw4w9WgXcQ/image/0"
  }
]
```

---

#### `GET /api/slides/{vid_id}`
특정 영상의 슬라이드 목록 (OCR 텍스트 포함, 이미지 BLOB 제외).

**Response:**
```json
{
  "video_id": "dQw4w9WgXcQ",
  "title": "영상 제목",
  "total_slides": 42,
  "slides": [
    {
      "slide_index": 0,
      "timestamp": 12.5,
      "time_str": "0:12",
      "filename": "slide_000.jpg",
      "ocr_text": "슬라이드에서 추출된 텍스트",
      "llm_summary": ""
    }
  ]
}
```

---

#### `GET /api/slides/{vid_id}/image/{filename}`
슬라이드 이미지를 DB에서 직접 서빙. `filename`은 파일명 또는 slide_index(정수) 모두 허용.

**Response:** `image/jpeg` 바이너리

```
GET /api/slides/dQw4w9WgXcQ/image/0          # index로 조회
GET /api/slides/dQw4w9WgXcQ/image/slide_000.jpg  # 파일명으로 조회
```

---

#### `GET /api/slides/search?q={keyword}`
모든 영상의 OCR 텍스트 전문 검색. 최대 200건 반환.

**Query Params:**
| 파라미터 | 설명 |
|---------|------|
| `q` | 검색어 (ILIKE 부분 일치) |

**Response:**
```json
[
  {
    "vid_id": "dQw4w9WgXcQ",
    "title": "영상 제목",
    "slide_index": 5,
    "filename": "slide_005.jpg",
    "time_str": "1:23",
    "ocr_text": "전체 OCR 텍스트",
    "match_excerpt": "...검색어가 포함된 전후 160자..."
  }
]
```

---

#### `DELETE /api/slides/{vid_id}/slide/{slide_index}`
특정 슬라이드 DB에서 삭제.

---

### Q&A

#### `POST /api/qa/{video_id}`
영상 트랜스크립트를 컨텍스트로 LLM 질의응답. 무료 사용자는 일 10회 제한.

**Request Body:**
```json
{
  "question": "이 영상에서 말하는 핵심 메시지는 무엇인가요?",
  "language": "ko"
}
```

**Response:**
```json
{
  "answer": "AI가 생성한 답변 텍스트",
  "quota_remaining": 8,
  "quota_type": "free",
  "video_id": "dQw4w9WgXcQ"
}
```

**Error (쿼터 초과):**
```json
HTTP 429
{
  "error": "quota_exceeded",
  "message": "일일 무료 제한(10회) 초과. 유료 업그레이드가 필요합니다.",
  "quota_remaining": 0
}
```

---

#### `GET /api/qa/{video_id}/history`
특정 영상에 대한 현재 사용자의 Q&A 이력 조회.

**Query Params:**
| 파라미터 | 기본값 | 설명 |
|---------|--------|------|
| `limit` | 20 | 최대 100 |
| `user_id` | (요청자) | 다른 사용자 ID 지정 가능 |

---

#### `GET /api/quota/status`
현재 사용자의 쿼터 상태 조회.

**Response:**
```json
{
  "user_id": "anon:127.0.0.1",
  "quota_type": "free",
  "daily_used": 2,
  "daily_limit": 10,
  "quota_remaining": 8,
  "total_used": 50
}
```

---

#### `POST /api/quota/upgrade/{user_id}`
사용자를 premium으로 업그레이드. Stripe 웹훅 또는 관리자 호출용.

---

### AI 분석 작업

#### `POST /api/ai-tasks`
영상 트랜스크립트 기반 AI 분석 작업 생성 (요약, 번역, 리포트 등).

**Request Body:**
```json
{
  "video_ids": ["vid1", "vid2"],
  "prompt": "이 영상의 핵심 내용을 3줄로 요약해주세요.",
  "output_type": "markdown",
  "model": "sonnet",
  "parent_task_id": null
}
```

`model` 값: `haiku` | `sonnet` | `opus`  
`parent_task_id`: 이전 분석 결과를 컨텍스트로 활용하는 후속 질문용

---

#### `GET /api/ai-tasks`
AI 작업 이력 목록 (최근 100건).

#### `GET /api/ai-tasks/{ai_task_id}`
특정 AI 작업 상세 + 결과 전문.

#### `GET /api/ai-tasks/{ai_task_id}/download`
분석 결과를 `.md` 또는 `.txt` 파일로 다운로드.

---

### 동시처리 제어

#### `GET /api/concurrency`
현재 동시 처리 한도 및 실행 중/대기 중 작업 수 조회.

**Response:**
```json
{
  "max_concurrent": 3,
  "running": 1,
  "pending": 0
}
```

---

#### `POST /api/concurrency`
동시 처리 한도 변경 (런타임 즉시 적용).

**Request Body:**
```json
{ "max_concurrent": 5 }
```

---

### 헬스체크 / 유지보수

#### `GET /api/health`
서버 상태 + 임시 파일 사용량 조회.

**Response:**
```json
{
  "status": "ok",
  "temp_usage_mb": 124.3,
  "cleanup_policy": "48시간 후 자동 삭제"
}
```

---

#### `POST /api/cleanup`
48시간 이상 된 임시 파일 수동 삭제 (`/tmp/stt-work`, `/tmp/mind_mingle`).

#### `POST /api/cleanup/force`
모든 임시 파일 즉시 강제 삭제.

---

### 내부 API

| 엔드포인트 | 설명 |
|-----------|------|
| `POST /internal/llm-callback/{request_id}` | LLM 게이트웨이 비동기 콜백 수신 |
| `POST /internal/recorrect/{video_id}` | 특정 영상 트랜스크립트 재교정 |

---

## 로컬 개발 환경 설정

### 사전 요구사항

```bash
# 시스템 패키지 (macOS)
brew install yt-dlp ffmpeg tesseract tesseract-lang

# Python 3.10+
python3 --version

# Node.js 20+
node --version
```

### 1. 저장소 클론

```bash
git clone <repo-url>
cd offline-thinking
```

### 2. DB 설정 (Docker 사용 시)

로컬 Supabase 인스턴스가 있으면 그대로 사용한다. 없으면 Docker로 독립 PostgreSQL을 실행한다.

```bash
# Docker로 DB 실행 (port 54399)
docker compose -f docker-compose.db.yml up -d

# 마이그레이션 실행 (Supabase 공유 인스턴스 사용 시, port 54322)
psql -h localhost -p 54322 -U postgres -d postgres \
  -f api/migrations/init_schema.sql \
  -f api/migrations/add_ocr_columns.sql \
  -f api/migrations/add_upload_date.sql \
  -f api/migrations/add_qa_quota.sql
```

### 3. 백엔드 설정

```bash
cd api

# 가상환경 생성 및 활성화
python3 -m venv venv
source venv/bin/activate

# 의존성 설치
pip install -r requirements.txt

# 환경변수 설정
cp .env.example .env
# .env 편집 (DB 접속 정보, LLM 게이트웨이 URL 등)

# 서버 실행
uvicorn main:app --host 0.0.0.0 --port 9102 --reload
```

API 서버 확인: http://localhost:9102/api/health  
Swagger UI: http://localhost:9102/docs

### 4. 프론트엔드 설정

```bash
cd web

# 의존성 설치
npm ci --ignore-scripts

# 개발 서버 실행
npm run dev
```

프론트엔드 확인: http://localhost:3204

### 5. 동작 확인

```bash
# YouTube URL 분석 요청
curl -X POST http://localhost:9102/api/transcribe/youtube \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.youtube.com/watch?v=YOUR_VIDEO_ID", "language": "ko"}'

# 응답: {"task_id": "abc123"}

# 진행 상태 확인
curl http://localhost:9102/api/tasks/abc123
```

---

## 프로덕션 배포

### 권장 아키텍처

| 컴포넌트 | 권장 플랫폼 | 비고 |
|---------|------------|------|
| 프론트엔드 (Next.js) | Vercel | `npm run build` 후 배포 |
| 백엔드 (FastAPI) | Railway / Fly.io | Dockerfile 필요 (현재 미포함) |
| DB (PostgreSQL) | Supabase Cloud | 마이그레이션 SQL 그대로 사용 가능 |
| LLM 게이트웨이 | 별도 VPS 또는 Public URL 확보 | 현재 localhost:3100 의존 |

### STT 환경 분기

| 환경 | STT 엔진 | 설정 방법 |
|------|---------|----------|
| 로컬 (Apple Silicon) | mlx-whisper | 기본값, 별도 설정 불필요 |
| 클라우드 (Linux CPU) | faster-whisper | `USE_FASTER_WHISPER=true` 환경변수 설정 후 transcribe.py 분기 처리 |
| 클라우드 (브라우저) | WebGPU Whisper | 프론트엔드 직접 처리 (별도 구현 필요) |

> **주의:** mlx-whisper는 Apple Silicon 전용이다. Linux 서버에서 그대로 실행하면 매우 느리거나 오류가 발생한다.

### 배포 시 체크리스트

```
[ ] .env에 SUPABASE_JWT_SECRET 설정 → auth.py JWT 검증 활성화
[ ] .env에 STRIPE_SECRET_KEY 설정 → stripe_payments.py 활성화
[ ] LLM 게이트웨이 Public URL 확보 → GATEWAY_URL 환경변수 변경
[ ] API_BASE_URL을 실제 도메인으로 변경 (LLM 콜백 URL 생성용)
[ ] CORS origin 설정 (main.py allow_origins에 프론트 도메인 추가)
[ ] STT 엔진 분기 설정 (Apple Silicon → cloud 환경 변경 시)
[ ] 임시 파일 정리 주기 확인 (기본: 48시간)
```

---

## 환경변수

`api/.env` 파일에 설정한다.

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `DB_HOST` | `localhost` | PostgreSQL 호스트 |
| `DB_PORT` | `54322` | PostgreSQL 포트 |
| `DB_NAME` | `postgres` | DB 이름 |
| `DB_USER` | `postgres` | DB 사용자 |
| `DB_PASSWORD` | `postgres` | DB 비밀번호 |
| `GATEWAY_URL` | `http://localhost:3100/api/plugins/llm-gateway/webhooks/process` | LLM 게이트웨이 URL |
| `API_BASE_URL` | `http://localhost:8000` | LLM 콜백 수신 URL (자신의 공개 URL) |
| `CLAUDE_BIN` | `/opt/homebrew/bin/claude` | claude CLI 경로 (게이트웨이 폴백용) |
| `SUPABASE_JWT_SECRET` | `""` | Supabase Auth JWT 시크릿 (프로덕션 필수) |
| `STRIPE_SECRET_KEY` | `""` | Stripe 시크릿 키 (결제 활성화 시 필수) |
| `FREE_DAILY_LIMIT` | `10` | 무료 사용자 일일 Q&A 제한 횟수 |

---

## 프로젝트 구조

```
offline-thinking/
├── api/                          # FastAPI 백엔드
│   ├── main.py                   # 앱 엔트리포인트, 라우터 등록, 임시파일 정리
│   ├── auth.py                   # 인증 (현재: X-User-Id 헤더, 향후: Supabase JWT)
│   ├── db.py                     # PostgreSQL 연결 + query/execute 헬퍼
│   ├── llm_gateway.py            # LLM 게이트웨이 클라이언트 (비동기 콜백)
│   ├── vtt_pipeline.py           # VTT 다운로드 + 파싱 + LLM 교정 파이프라인
│   ├── transcribe.py             # Whisper STT 래퍼
│   ├── slide_capture.py          # ffmpeg 장면 감지 + 프레임 추출
│   ├── ocr_pipeline.py           # pytesseract OCR + 중복 제거
│   ├── batch_slides_playlist.py  # 영상별 슬라이드 일괄 처리
│   ├── stripe_payments.py        # Stripe 결제 스켈레톤
│   ├── routers/
│   │   ├── stt.py                # /api/transcribe/* (YouTube URL, 파일 업로드)
│   │   ├── slides.py             # /api/slides/* (목록, 이미지, OCR 검색)
│   │   ├── qa.py                 # /api/qa/*, /api/quota/*
│   │   ├── tasks.py              # /api/ai-tasks/* (AI 분석 작업)
│   │   ├── collections.py        # /api/collections/* (채널/재생목록 수집)
│   │   ├── playlists.py          # /api/playlists/*
│   │   ├── search.py             # /api/search/*
│   │   ├── share.py              # /api/share/*
│   │   ├── docs.py               # /api/docs/*
│   │   └── batch_slides.py       # /api/batch-slides/*
│   ├── services/
│   │   └── task_manager.py       # 비동기 태스크 + 세마포어 + SSE 스트리밍
│   └── migrations/
│       ├── init_schema.sql       # 초기 스키마 (collections, videos, transcripts, ai_tasks, shares)
│       ├── add_ocr_columns.sql   # transcripts OCR 컬럼 추가
│       ├── add_upload_date.sql   # videos.upload_date 추가
│       ├── add_qa_quota.sql      # user_quota, qa_history 테이블 추가
│       ├── add_playlists.sql     # 재생목록 관련 테이블 추가
│       └── add_pgvector.sql      # pgvector 확장 (RAG 준비)
├── web/                          # Next.js 16 프론트엔드
│   ├── app/                      # App Router
│   ├── components/               # UI 컴포넌트
│   └── lib/                      # API 클라이언트, 유틸리티
├── docker-compose.db.yml         # 독립 PostgreSQL (port 54399)
├── requirements.txt              # Python 의존성 (최상위, venv 참조용)
└── harness/                      # 개발 규약 + 아키텍처 문서
```

---

## 유료화 모델

| 플랜 | 가격 | Q&A 한도 | 기타 |
|------|------|---------|------|
| **Free** | 무료 | 일 10회 | 영상 분석, 슬라이드 캡처 무제한 |
| **Premium** | (Stripe 결제) | 무제한 | - |

### 현재 구현 상태

- `user_quota` 테이블: 일일 사용량 추적, 날짜 자동 리셋 ✅
- `qa_history` 테이블: Q&A 이력 기록 ✅
- `stripe_payments.py`: Stripe 결제 스켈레톤 구현 완료 (미활성)
- `POST /api/quota/upgrade/{user_id}`: 관리자 수동 업그레이드 ✅
- Supabase Auth JWT 검증: 스켈레톤 구현 완료 (미활성)

---

## 라이선스 및 문의

비즈니스 문의 및 라이선스: **sales@com.dooray.com**
