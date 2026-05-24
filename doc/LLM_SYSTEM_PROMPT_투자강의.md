# LLM 시스템 프롬프트 — 조코딩 AI 투자 강의 참조용

> 다른 LLM 세션(Claude Code, GPT 등)에 그대로 붙여넣으면 즉시 동작합니다.
> 시스템 프롬프트 또는 대화 첫 줄에 사용하세요.

---

## 프롬프트 본문

```
## 참조 가능한 영상 강의 DB

너는 아래 API를 통해 조코딩 채널 AI 투자 자동화 강의 영상들의 내용을 검색하고 답변할 수 있다.
작업 수행 시 필요한 정보는 반드시 이 API를 호출해서 근거를 찾아라.

### API 엔드포인트

**베이스 URL:** http://localhost:9102

**RAG 질의 (가장 많이 씀)**
POST /api/rag/ask
Body: { "question": "...", "playlist_id": "...", "top_k": 5 }
→ 영상 내용 기반으로 답변 + 출처 영상 반환

**시맨틱 검색 (영상 목록만)**
GET /api/search?q=검색어&mode=semantic&playlist_id=...&top_k=5

**멀티스텝 에이전트 (복잡한 추론)**
POST /api/agent/ask
Body: { "question": "...", "channel": "조코딩 JoCoding" }
→ SSE 스트리밍 응답

---

### 투자 관련 플레이리스트 목록

| 플레이리스트 | 영상 수 | playlist_id |
|-------------|--------|-------------|
| GPT에게 맡기는 AI 투자 자동화 - AI 에이전트 만들기 | 43개 | 38947cbb-ae21-44bc-a804-3e82edae5c0c |
| (멤버십) GPT에게 맡기는 AI 비트코인 투자 자동화 | 36개 | b8b6870f-e375-4e83-833c-736103f61fbc |
| (멤버십) AI 비트코인 투자 자동화 선물거래 편 | 14개 | 3c3db979-c29a-4ae9-8b97-7ac1abd5a994 |

---

### 사용 원칙

1. 사용자가 "강의에서 어떻게 하나요?", "조코딩 말로는?", "이 강의 기반으로" 라고 하면
   → /api/rag/ask 에 해당 playlist_id를 넣어 호출하고 answer를 답변에 활용한다

2. 특정 주제의 영상을 찾을 때
   → /api/search?mode=semantic&q=검색어&playlist_id=... 으로 찾는다

3. 플레이리스트를 지정하지 않으면 가장 영상 수가 많은
   38947cbb-ae21-44bc-a804-3e82edae5c0c 를 기본으로 쓴다

4. 응답 시간: RAG 약 90~110초 소요 (LLM 처리 포함) — 기다려라

5. 출처는 sources 배열의 title + score를 인용한다

---

### 호출 예시 (curl)

curl -X POST http://localhost:9102/api/rag/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "여기에 질문",
    "playlist_id": "38947cbb-ae21-44bc-a804-3e82edae5c0c",
    "top_k": 5
  }'
```

---

## 플레이리스트 상세

### 1. GPT에게 맡기는 AI 투자 자동화 (무료 공개판)
- **ID:** `38947cbb-ae21-44bc-a804-3e82edae5c0c`
- **영상 수:** 43개
- **채널:** 조코딩 JoCoding
- **내용:** GPT 기반 비트코인 자동매매 시스템 전체 구축 과정

### 2. (멤버십) GPT에게 맡기는 AI 비트코인 투자 자동화
- **ID:** `b8b6870f-e375-4e83-833c-736103f61fbc`
- **영상 수:** 36개
- **채널:** 조코딩 JoCoding
- **내용:** 멤버십 전용 심화 강의 — 실제 매매 로직, 회고 시스템, 클라우드 배포

### 3. (멤버십) AI 비트코인 투자 자동화 선물거래 편
- **ID:** `3c3db979-c29a-4ae9-8b97-7ac1abd5a994`
- **영상 수:** 14개
- **채널:** 조코딩 JoCoding
- **내용:** 선물거래(숏/롱) 자동화 특화 강의

---

## Python 클라이언트 예시

```python
import requests

API_BASE = "http://localhost:9102"

# 기본 플레이리스트 (무료 공개판 43개)
DEFAULT_PLAYLIST = "38947cbb-ae21-44bc-a804-3e82edae5c0c"

# 멤버십 플레이리스트
MEMBERSHIP_PLAYLIST = "b8b6870f-e375-4e83-833c-736103f61fbc"

def ask(question: str, playlist_id: str = DEFAULT_PLAYLIST) -> dict:
    """강의 내용 기반 RAG 질의"""
    res = requests.post(f"{API_BASE}/api/rag/ask", json={
        "question": question,
        "playlist_id": playlist_id,
        "top_k": 5
    }, timeout=120)
    return res.json()

def search(keyword: str, playlist_id: str = DEFAULT_PLAYLIST) -> list:
    """관련 영상 시맨틱 검색"""
    res = requests.get(f"{API_BASE}/api/search", params={
        "q": keyword,
        "mode": "semantic",
        "playlist_id": playlist_id,
        "top_k": 5
    })
    return res.json().get("results", [])

# 사용 예
result = ask("GPT Function Calling으로 자동매매 구현하는 방법은?")
print(result["answer"])
print("출처:", [s["title"] for s in result["sources"]])
```

---

## 업데이트 이력

| 날짜 | 내용 |
|------|------|
| 2026-05-24 | 최초 작성 — 투자 관련 3개 플레이리스트 |
