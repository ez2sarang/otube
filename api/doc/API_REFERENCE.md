# Offline Thinking API Reference

## Overview

FastAPI backend serving the Offline Thinking SaaS platform.
Base URL: `http://localhost:9102`

---

## Health & Cleanup

### Health Check
```
GET /api/health
```
Returns server status and temporary file usage.

**Response:**
```json
{
  "status": "ok",
  "temp_usage_mb": 123.4,
  "cleanup_policy": "48시간 후 자동 삭제"
}
```

### Manual Cleanup
```
POST /api/cleanup
```
Manually trigger cleanup of old temporary files.

### Force Cleanup
```
POST /api/cleanup/force
```
Force delete all temporary files immediately.

---

## STT (Speech-to-Text)

### Submit STT Task
```
POST /api/stt/submit
```
Upload video and submit for STT processing.

**Body:**
```json
{
  "video_url": "https://youtube.com/watch?v=...",
  "language": "ko"
}
```
※ **language**: 자막/음성 인식 언어 코드. `"ko"` = 한국어, `"en"` = 영어. 기본값 `"ko"`.

---

## Collections

### List Collections
```
GET /api/collections
```

### Create Collection
```
POST /api/collections
```

### Delete Collection
```
DELETE /api/collections/{collection_id}
```

---

## Videos & Transcripts

### List Videos
```
GET /api/videos
```

### Get Video Details
```
GET /api/videos/{video_id}
```

### Get Transcript
```
GET /api/videos/{video_id}/transcript
```

---

## Q&A (Question & Answer)

### Submit Question
```
POST /api/qa/questions
```
Ask a question about a video's transcript.

**Body:**
```json
{
  "video_id": "...",
  "question": "What is the main topic?"
}
```

**Response:**
```json
{
  "question_id": "...",
  "answer": "...",
  "tokens_used": 150
}
```

### List Questions
```
GET /api/qa/questions?video_id=...
```

---

## Search

### Search Transcripts
```
GET /api/search?q=keyword&mode=semantic&top_k=10&channel=...&playlist_id=...
```

**파라미터 설명:**

| 파라미터 | 필수 | 설명 |
|---------|------|------|
| `q` | ✅ | 검색어 |
| `mode` | — | `"semantic"` = 의미 기반 유사도 검색 (벡터 DB), `"keyword"` = 단어 포함 검색 (ILIKE). 기본값 `"semantic"` |
| `top_k` | — | 반환할 결과 영상 수. `5` = 상위 5개만 반환. 기본값 10, 최대 100 |
| `channel` | — | 특정 채널로 결과 필터. 예: `"조코딩 JoCoding"` |
| `playlist_id` | — | 특정 플레이리스트 내에서만 검색. UUID 형식 (예: `38947cbb-ae21-44bc-a804-3e82edae5c0c`) |

---

## LangGraph 멀티스텝 에이전트

### LangGraph란?

LangChain이 만든 **상태 기반 AI 워크플로우 프레임워크**입니다.
일반 RAG(검색 → 답변 1회)와 달리, LangGraph는 노드(Node)와 엣지(Edge)로 구성된
그래프 구조를 정의하여 **조건에 따라 다시 시도하거나 분기**할 수 있습니다.

> RAG와의 차이:
> - **RAG**: 검색 → 답변 생성 → 끝 (1회성, 빠름)
> - **LangGraph**: 검색 → 답변 생성 → 품질 평가 → 부족하면 재시도 (반복, 정확함)

---

### 이 프로젝트에서의 구조

파일: `api/agent_graph.py`

```
[retrieve] → [generate] → [grade] → GOOD → END
                 ↑            |
                 └── RETRY ───┘  (최대 3회)
```

**노드별 역할:**

| 노드 | 역할 | 사용 모델 |
|------|------|---------|
| `retrieve` | pgvector로 질문과 관련된 영상 상위 10개 검색 → 상위 5개 트랜스크립트 수집 | — (DB 검색) |
| `generate` | 수집된 트랜스크립트를 컨텍스트로 LLM에게 답변 생성 요청 | Claude Sonnet |
| `grade` | 생성된 답변이 질문에 충분히 답했는지 LLM이 평가 ("good" / "retry") | Claude Haiku |

**조건부 엣지:**
- `grade → "good"` → 그래프 종료, 답변 반환
- `grade → "retry"` → `retrieve` 노드로 돌아가 재시도 (최대 3회, 이후 강제 종료)

---

### API 엔드포인트

```
POST /api/agent/ask
```

**Body:**
```json
{
  "question": "비트코인 자동매매 시스템의 핵심 3요소는?",
  "channel": "조코딩 JoCoding"
}
```

※ **channel**: 검색 범위를 특정 채널로 제한. 생략 시 전체 영상 대상.
※ **응답 방식**: SSE 스트리밍 (연결 유지하며 실시간 진행 상황 수신)

**SSE 이벤트 흐름:**
```
data: {"status": "searching", "message": "영상 검색 중..."}
data: {"status": "generating", "message": "답변 생성 중..."}
data: {"status": "complete", "result": {"answer": "...", "video_ids": [...], "retrieved_docs": [...]}}
```

**curl 예시:**
```bash
curl -X POST http://localhost:9102/api/agent/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "GPT 자동매매 핵심 구조는?", "channel": "조코딩 JoCoding"}'
```

**응답 시간:** 약 150~200초 (retrieve + generate + grade 각 ~60초 타임아웃)

---

### RAG vs LangGraph 비교

| 항목 | RAG (`/api/rag/ask`) | LangGraph (`/api/agent/ask`) |
|------|---------------------|------------------------------|
| 흐름 | 검색 → 생성 (1회) | 검색 → 생성 → 평가 → 재시도 |
| 응답 속도 | ~90~110초 | ~150~200초 |
| 답변 품질 | 단순 참고 기반 | 자기 평가로 품질 보장 |
| 사용 권장 | 빠른 답변이 필요할 때 | 정확도가 중요한 복잡한 질문 |
| playlist_id 지원 | ✅ | ❌ (channel만 지원) |

---

## Slides

### List Video Slides
```
GET /api/videos/{video_id}/slides
```

### Get Slide Details
```
GET /api/slides/{slide_id}
```

---

## Playlists

### List Playlists
```
GET /api/playlists
```

### Create Playlist
```
POST /api/playlists
```

---

## Task Events (Server-Sent Events)

> **SSE(Server-Sent Events)란?**
> 서버가 클라이언트로 데이터를 일방향으로 실시간 밀어주는 방식.
> 일반 HTTP 요청은 요청 → 응답 1회로 끝나지만, SSE는 연결을 유지하면서
> 서버가 준비될 때마다 데이터를 조금씩 보냄.
> LLM 답변처럼 오래 걸리는 작업의 진행률을 실시간으로 받을 때 사용.
> 브라우저 기준: `EventSource` API 또는 `fetch` + `ReadableStream`으로 수신.

### 작업 상태 조회 (단발성)
```
GET /api/tasks/{task_id}
```
Returns current task status as JSON. 폴링(반복 요청)용.

**Response:**
```json
{
  "task_id": "a1b2c3d4",
  "status": "running",
  "message": "AI 처리 중...",
  "progress": 40,
  "result": null,
  "error": null
}
```
※ **status**: `"pending"` → `"running"` → `"done"` / `"error"` 순으로 전환.

### Stream Task Progress (실시간 스트리밍)
```
GET /api/tasks/{task_id}/events
```

Returns task progress as Server-Sent Events (SSE).

**수신 예시 (curl):**
```bash
curl -N http://localhost:9102/api/tasks/{task_id}/events
# data: {"status": "running", "message": "트랜스크립트 로딩 중...", "progress": 10}
# data: {"status": "running", "message": "AI 처리 중...", "progress": 40}
# data: {"status": "done", "message": "완료", "progress": 100, "result": {...}}
```

---

## Error Responses

All endpoints return error responses in this format:

```json
{
  "detail": "Error message"
}
```

HTTP Status Codes:
- `200 OK` — Success
- `400 Bad Request` — Invalid input
- `404 Not Found` — Resource not found
- `500 Internal Server Error` — Server error

---

## Rate Limiting

Currently no rate limiting. Planned: token-based quotas for Q&A endpoints.

---

## Internal Endpoints

### LLM Gateway Callback
```
POST /internal/llm-callback/{request_id}
```
Internal endpoint for LLM gateway to send responses.

### Recorrect Transcript
```
POST /internal/recorrect/{video_id}
```
Rebuild corrected transcript with latest LLM prompt.

---

## 실전 시뮬레이션 결과 (2026-05-24)

조코딩 채널 "(멤버십) GPT에게 맡기는 AI 비트코인 투자 자동화" 플레이리스트 36개 영상 대상으로
외부 클라이언트 HTTP 테스트를 실행한 결과입니다.

**playlist_id:** `b8b6870f-e375-4e83-833c-736103f61fbc`

| 테스트 | 엔드포인트 | 응답시간 | 결과 |
|--------|-----------|---------|------|
| 시맨틱 검색 | `GET /api/search?mode=semantic` | 35ms | ✅ 정상 |
| 키워드 검색 | `GET /api/search?mode=keyword` | 91ms | ✅ 정상 |
| RAG 답변 생성 | `POST /api/rag/ask` | ~105초 | ✅ 정상 |
| LangGraph 에이전트 | `POST /api/agent/ask` | ~180초 | ✅ 정상 |
| 플레이리스트 영상 목록 | `GET /api/playlists/{id}/videos` | 146ms | ✅ 정상 |

### RAG 답변 샘플

**질문:** "이 강의에서 AI 에이전트가 비트코인 투자를 자동화하는 핵심 구조는?"

```
핵심 구조 (5단계 사이클)
1. 데이터 수집 — 차트 데이터, 뉴스, 공포 탐욕 지수, 유튜브 자막, 과거 매매 기록
2. AI 판단    — GPT가 매수/매도/홀드 + 투자비율(%) + 이유(reason) 결정
3. 실제 매매  — 업비트 API로 실행
4. 기록 & 회고 — 매매 기록 저장 + GPT가 일기 형식으로 회고 작성
5. 피드백    — 회고를 다음 판단 데이터로 재투입 (순환 학습)
```

출처 영상 상위 5개: EOnaOpZy9ew (0.892), OM8orP1lHBA (0.891), 7pJgdLZ9ydU (0.889), RhW8303hyQ0 (0.888), yPBiLsav6_o (0.873)

---

## LLM 작업 실행용 시스템 프롬프트

다른 LLM 세션(Claude Code, GPT 등)에 붙여넣으면 즉시 이 API를 활용할 수 있습니다.

```
## 참조 가능한 영상 강의 DB

너는 아래 API를 통해 조코딩 채널 AI 투자 자동화 강의 영상들의 내용을 검색하고 답변할 수 있다.
작업 수행 시 필요한 정보는 반드시 이 API를 호출해서 근거를 찾아라.

**베이스 URL:** http://localhost:9102

**RAG 질의** → POST /api/rag/ask
Body: { "question": "...", "playlist_id": "...", "top_k": 5 }
  ※ playlist_id: 검색 범위를 특정 플레이리스트로 제한하는 UUID. 아래 목록 참고.
  ※ top_k: 답변 생성에 참고할 영상 수. 5 = 가장 관련도 높은 영상 5개를 컨텍스트로 사용.
     숫자가 클수록 더 넓은 범위를 참고하지만 응답 시간이 길어짐. 권장: 3~10

**시맨틱 검색** → GET /api/search?q=검색어&mode=semantic&playlist_id=...&top_k=5
  ※ mode: semantic = 문장 의미 기반 검색 (벡터 유사도), keyword = 단어 포함 여부 검색
  ※ top_k: 반환할 검색 결과 영상 수. 5 = 유사도 상위 5개 영상만 반환.

**멀티스텝 에이전트** → POST /api/agent/ask
Body: { "question": "...", "channel": "조코딩 JoCoding" }
  ※ channel: 특정 채널 내 영상으로만 검색 범위 제한. 생략 시 전체 영상 대상.
  ※ 응답 방식: SSE 스트리밍 (연결 유지하며 진행 상황 실시간 수신. 자세한 내용은 Task Events 섹션 참고)

투자 관련 플레이리스트:
- GPT AI 투자 자동화 (43개): 38947cbb-ae21-44bc-a804-3e82edae5c0c  ← 기본값
- (멤버십) 비트코인 투자 자동화 (36개): b8b6870f-e375-4e83-833c-736103f61fbc
- (멤버십) 선물거래 편 (14개): 3c3db979-c29a-4ae9-8b97-7ac1abd5a994

사용 원칙:
1. "강의에서 어떻게?", "이 강의 기반으로" → /api/rag/ask 호출
2. 특정 주제 영상 찾기 → /api/search?mode=semantic
3. 응답 시간: RAG 약 90~110초 — 기다려라
4. 출처는 sources 배열의 title + score를 인용한다
```

> 전체 프롬프트 파일: `doc/LLM_SYSTEM_PROMPT_투자강의.md`

---

## Documentation

- **API Docs (Swagger UI)**: http://localhost:9102/docs
- **OpenAPI Schema**: http://localhost:9102/openapi.json
- **API Reference (Markdown)**: http://localhost:9102/api/docs/reference
- **API Reference (HTML)**: http://localhost:9102/api/docs/reference.html
