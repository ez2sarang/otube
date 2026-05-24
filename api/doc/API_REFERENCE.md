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
GET /api/search?q=keyword
```

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

### Stream Task Progress
```
GET /api/tasks/{task_id}/events
```

Returns task progress as Server-Sent Events (SSE).

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

## Documentation

- **API Docs (Swagger UI)**: http://localhost:9102/docs
- **OpenAPI Schema**: http://localhost:9102/openapi.json
- **API Reference (Markdown)**: http://localhost:9102/api/docs/reference
- **API Reference (HTML)**: http://localhost:9102/api/docs/reference.html
