"""검색 + RAG + 에이전트 라우터"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List
import json
import asyncio

from db import query
import rag_pipeline
import agent_graph

router = APIRouter(prefix="/api")


# --- Request/Response Models ---

class SearchRequest(BaseModel):
    q: str
    mode: str = "semantic"  # "semantic" | "keyword"
    top_k: int = 10
    channel: Optional[str] = None
    playlist_id: Optional[str] = None


class RagAskRequest(BaseModel):
    question: str
    channel: Optional[str] = None
    playlist_id: Optional[str] = None
    top_k: int = 5


class AgentAskRequest(BaseModel):
    question: str
    channel: Optional[str] = None


# --- GET /api/search ---

@router.get("/search")
async def search(
    q: str = Query(...),
    mode: str = Query("semantic"),
    top_k: int = Query(10),
    channel: Optional[str] = Query(None),
    playlist_id: Optional[str] = Query(None),
):
    """
    영상 검색 (의미론적 또는 키워드).

    Query parameters:
        q: 검색어
        mode: "semantic" (pgvector) | "keyword" (ILIKE)
        top_k: 결과 개수
        channel: 채널 필터
        playlist_id: 플레이리스트 필터

    Returns:
        [{video_id, title, channel, score/snippet}]
    """
    if not q or not q.strip():
        raise HTTPException(status_code=400, detail="q (search query) is required")

    if mode == "semantic":
        results = rag_pipeline.semantic_search(
            q, top_k=top_k, channel=channel, playlist_id=playlist_id
        )
    elif mode == "keyword":
        # 키워드 검색 (SQL ILIKE)
        sql = """
            SELECT
                t.video_id,
                v.title,
                v.channel,
                SUBSTRING(t.full_text, 1, 150) AS snippet
            FROM stt_analysis.transcripts t
            JOIN stt_analysis.videos v ON t.video_id = v.video_id
            WHERE t.full_text ILIKE %s
        """
        params = [f"%{q}%"]

        if channel:
            sql += " AND v.channel = %s"
            params.append(channel)

        if playlist_id:
            sql += """
                AND t.video_id IN (
                    SELECT video_id FROM stt_analysis.video_playlists
                    WHERE playlist_id = %s
                )
            """
            params.append(playlist_id)

        sql += f" LIMIT {min(top_k, 100)}"
        results = query(sql, tuple(params))
        results = [dict(row) for row in results] if results else []
    else:
        raise HTTPException(status_code=400, detail='mode must be "semantic" or "keyword"')

    return {"query": q, "mode": mode, "count": len(results), "results": results}


# --- POST /api/rag/ask ---

@router.post("/rag/ask")
async def rag_ask(req: RagAskRequest):
    """
    RAG 기반 답변 생성.

    Body:
        question: 사용자 질문
        channel: 채널 필터 (옵션)
        playlist_id: 플레이리스트 필터 (옵션)
        top_k: 검색 결과 개수 (기본 5)

    Returns:
        {question, answer, video_ids, sources}
    """
    if not req.question or not req.question.strip():
        raise HTTPException(status_code=400, detail="question is required")

    # 의미론적 검색으로 관련 영상 찾기
    search_results = rag_pipeline.semantic_search(
        req.question,
        top_k=req.top_k,
        channel=req.channel,
        playlist_id=req.playlist_id,
    )

    if not search_results:
        return {
            "question": req.question,
            "answer": "관련 영상을 찾을 수 없습니다.",
            "video_ids": [],
            "sources": [],
        }

    video_ids = [r["video_id"] for r in search_results]

    # RAG 답변 생성
    answer = rag_pipeline.rag_answer(req.question, video_ids)

    return {
        "question": req.question,
        "answer": answer,
        "video_ids": video_ids,
        "sources": [
            {
                "video_id": r["video_id"],
                "title": r["title"],
                "channel": r["channel"],
                "score": float(r["score"]),
            }
            for r in search_results
        ],
    }


# --- POST /api/agent/ask (SSE 스트리밍) ---

async def agent_stream(question: str, channel: Optional[str] = None):
    """에이전트 실행 후 SSE로 스트리밍"""
    try:
        # 에이전트 실행 (동기)
        result = agent_graph.run_agent(question, channel=channel)

        # 진행 상황 스트리밍
        yield f"data: {json.dumps({'status': 'searching', 'message': '영상 검색 중...'})}\n\n"
        await asyncio.sleep(0.1)

        yield f"data: {json.dumps({'status': 'generating', 'message': '답변 생성 중...'})}\n\n"
        await asyncio.sleep(0.1)

        # 최종 결과
        yield f"data: {json.dumps({'status': 'complete', 'result': result})}\n\n"

    except Exception as e:
        yield f"data: {json.dumps({'status': 'error', 'message': str(e)})}\n\n"


@router.post("/agent/ask")
async def agent_ask(req: AgentAskRequest):
    """
    LangGraph 에이전트 기반 멀티스텝 Q&A (SSE 스트리밍).

    Body:
        question: 사용자 질문
        channel: 채널 필터 (옵션)

    Returns:
        StreamingResponse (Server-Sent Events)
    """
    if not req.question or not req.question.strip():
        raise HTTPException(status_code=400, detail="question is required")

    return StreamingResponse(
        agent_stream(req.question, channel=req.channel),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
