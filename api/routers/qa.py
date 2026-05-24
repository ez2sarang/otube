"""영상 기반 LLM Q&A API 라우터"""
from fastapi import APIRouter, Request, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from datetime import date
from typing import Optional

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from db import query, query_one, execute
from llm_gateway import call_llm
from auth import get_user_id

router = APIRouter(prefix="/api")

FREE_DAILY_LIMIT = int(os.getenv("FREE_DAILY_LIMIT", "10"))


class QARequest(BaseModel):
    question: str
    language: str = "ko"


def _get_or_init_quota(user_id: str) -> tuple[str, int, int]:
    """user_quota 조회 + 날짜 리셋. (quota_type, daily_used, total_used) 반환"""
    today = date.today()
    row = query_one(
        "SELECT quota_type, daily_used, last_reset_date, total_used "
        "FROM stt_analysis.user_quota WHERE user_id = %s",
        (user_id,),
    )
    if not row:
        return "free", 0, 0

    daily_used = row["daily_used"]
    if row["last_reset_date"] != today:
        daily_used = 0
        execute(
            "UPDATE stt_analysis.user_quota SET daily_used = 0, last_reset_date = %s, updated_at = NOW() WHERE user_id = %s",
            (today, user_id),
        )
    return row["quota_type"], daily_used, row["total_used"]


@router.post("/qa/{video_id}")
async def ask_question(video_id: str, req: QARequest, request: Request):
    """
    영상 transcript를 컨텍스트로 LLM Q&A 처리.
    무료: 일 10회 / 유료(premium): 무제한
    """
    user_id = get_user_id(request)

    # 1. transcript + 영상 제목 조회 (JOIN)
    row = query_one(
        """
        SELECT t.corrected_text, t.full_text, v.title
        FROM stt_analysis.transcripts t
        JOIN stt_analysis.videos v ON v.id = t.video_id
        WHERE t.video_id = %s
        """,
        (video_id,),
    )
    if not row:
        raise HTTPException(status_code=404, detail=f"video not found: {video_id}")

    context = (row["corrected_text"] or row["full_text"] or "").strip()
    if not context:
        raise HTTPException(status_code=400, detail="transcript is empty")

    # 2. 쿼터 확인
    quota_type, daily_used, total_used = _get_or_init_quota(user_id)
    if quota_type == "free" and daily_used >= FREE_DAILY_LIMIT:
        return JSONResponse(
            status_code=429,
            content={
                "error": "quota_exceeded",
                "message": f"일일 무료 제한({FREE_DAILY_LIMIT}회) 초과. 유료 업그레이드가 필요합니다.",
                "quota_remaining": 0,
            },
        )

    # 3. LLM 답변 생성
    lang_label = "한국어" if req.language == "ko" else "English"
    task_prompt = (
        f"다음은 YouTube 영상 '{row['title']}' 의 스크립트입니다.\n"
        f"사용자 질문에 {lang_label}로 정확하고 간결하게 답변하세요.\n\n"
        f"질문: {req.question}"
    )
    answer = call_llm(task=task_prompt, text=context, model="haiku", timeout=30)
    if not answer:
        raise HTTPException(status_code=500, detail="LLM 응답 실패")

    # 4. 쿼터 소비 기록
    today = date.today()
    new_daily = daily_used + 1
    new_total = total_used + 1
    existing = query_one("SELECT user_id FROM stt_analysis.user_quota WHERE user_id = %s", (user_id,))
    if existing:
        execute(
            "UPDATE stt_analysis.user_quota SET daily_used=%s, total_used=%s, updated_at=NOW() WHERE user_id=%s",
            (new_daily, new_total, user_id),
        )
    else:
        execute(
            "INSERT INTO stt_analysis.user_quota(user_id,quota_type,daily_used,total_used,last_reset_date,created_at,updated_at) "
            "VALUES(%s,%s,%s,%s,%s,NOW(),NOW())",
            (user_id, "free", new_daily, new_total, today),
        )

    # 5. 히스토리 저장
    execute(
        "INSERT INTO stt_analysis.qa_history(user_id,video_id,question,answer,model,created_at) VALUES(%s,%s,%s,%s,%s,NOW())",
        (user_id, video_id, req.question, answer, "claude-haiku-4-5-20251001"),
    )

    quota_remaining = -1 if quota_type == "premium" else max(0, FREE_DAILY_LIMIT - new_daily)
    return {
        "answer": answer,
        "quota_remaining": quota_remaining,
        "quota_type": quota_type,
        "video_id": video_id,
    }


@router.get("/qa/{video_id}/history")
async def get_qa_history(
    video_id: str,
    request: Request,
    user_id: Optional[str] = Query(default=None),
    limit: int = Query(default=20, le=100),
):
    """특정 영상에 대한 Q&A 히스토리 조회"""
    uid = user_id or get_user_id(request)
    rows = query(
        "SELECT id, question, answer, model, created_at FROM stt_analysis.qa_history "
        "WHERE user_id=%s AND video_id=%s ORDER BY created_at DESC LIMIT %s",
        (uid, video_id, limit),
    )
    return {
        "video_id": video_id,
        "user_id": uid,
        "history": [
            {
                "id": r["id"],
                "question": r["question"],
                "answer": r["answer"],
                "model": r["model"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in rows
        ],
    }


@router.get("/quota/status")
async def get_quota_status(request: Request):
    """현재 사용자 쿼터 상태"""
    user_id = get_user_id(request)
    quota_type, daily_used, total_used = _get_or_init_quota(user_id)

    if quota_type == "premium":
        return {
            "user_id": user_id,
            "quota_type": "premium",
            "daily_used": daily_used,
            "daily_limit": -1,
            "quota_remaining": -1,
            "total_used": total_used,
        }
    return {
        "user_id": user_id,
        "quota_type": "free",
        "daily_used": daily_used,
        "daily_limit": FREE_DAILY_LIMIT,
        "quota_remaining": max(0, FREE_DAILY_LIMIT - daily_used),
        "total_used": total_used,
    }


@router.post("/quota/upgrade/{user_id}")
async def upgrade_to_premium(user_id: str, request: Request):
    """
    사용자를 premium으로 업그레이드 (Stripe 웹훅 또는 관리자 호출용).
    실제 서비스에서는 Stripe webhook에서 호출해야 함.
    """
    today = date.today()
    existing = query_one("SELECT user_id FROM stt_analysis.user_quota WHERE user_id = %s", (user_id,))
    if existing:
        execute(
            "UPDATE stt_analysis.user_quota SET quota_type='premium', updated_at=NOW() WHERE user_id=%s",
            (user_id,),
        )
    else:
        execute(
            "INSERT INTO stt_analysis.user_quota(user_id,quota_type,daily_used,total_used,last_reset_date,created_at,updated_at) "
            "VALUES(%s,'premium',0,0,%s,NOW(),NOW())",
            (user_id, today),
        )
    return {"ok": True, "user_id": user_id, "quota_type": "premium"}
