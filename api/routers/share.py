"""공유 링크 관련 API"""
import secrets

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from db import execute, query_one

router = APIRouter(prefix="/api")


def ensure_shares_table():
    """shares 테이블 없으면 생성"""
    try:
        execute("""
            CREATE TABLE IF NOT EXISTS stt_analysis.shares (
                token TEXT PRIMARY KEY,
                video_id TEXT NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                view_count INT DEFAULT 0
            )
        """)
    except Exception:
        pass


ensure_shares_table()


@router.post("/videos/{video_id}/share")
async def create_share(video_id: str):
    """영상 공유 링크 생성 (이미 있으면 기존 token 반환)"""
    # 이미 공유된 경우 기존 token 반환
    existing = query_one(
        "SELECT token FROM stt_analysis.shares WHERE video_id = %s",
        (video_id,)
    )
    if existing:
        return {"token": existing["token"]}

    token = secrets.token_urlsafe(16)
    execute(
        "INSERT INTO stt_analysis.shares (token, video_id) VALUES (%s, %s)",
        (token, video_id)
    )
    return {"token": token}


@router.get("/share/{token}")
async def get_share(token: str):
    """공유 토큰으로 영상 데이터 반환 (공개 엔드포인트)"""
    share = query_one(
        "SELECT video_id, created_at FROM stt_analysis.shares WHERE token = %s",
        (token,)
    )
    if not share:
        return JSONResponse({"error": "공유 링크가 유효하지 않습니다."}, status_code=404)

    video_id = share["video_id"]

    # 조회수 증가
    try:
        execute(
            "UPDATE stt_analysis.shares SET view_count = view_count + 1 WHERE token = %s",
            (token,)
        )
    except Exception:
        pass

    # 영상 정보
    video = query_one(
        """SELECT id, title, channel, url, duration_sec, text_length,
                  language, thumbnail, preview, upload_date
           FROM stt_analysis.videos WHERE id = %s""",
        (video_id,)
    )
    if not video:
        return JSONResponse({"error": "영상을 찾을 수 없습니다."}, status_code=404)

    # 트랜스크립트
    transcript = query_one(
        "SELECT corrected_text, full_text, segments FROM stt_analysis.transcripts WHERE video_id = %s",
        (video_id,)
    )
    full_text = ""
    segments = []
    if transcript:
        full_text = transcript["corrected_text"] or transcript["full_text"] or ""
        raw_segs = transcript["segments"]
        if raw_segs:
            import json as _json
            try:
                segments = _json.loads(raw_segs) if isinstance(raw_segs, str) else raw_segs
            except Exception:
                segments = []

    return {
        "video": dict(video),
        "transcript": full_text,
        "segments": segments,
        "created_at": share["created_at"].isoformat() if share["created_at"] else None,
    }
