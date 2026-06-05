"""슬라이드 뷰어 API — DB 저장 방식"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from db import query

router = APIRouter(prefix="/api")


@router.get("/slides-unprocessed")
async def list_slides_unprocessed():
    """STT DB에 없는 슬라이드 전용 영상 목록 (HistoryItem 호환 형식)"""
    rows = query("""
        SELECT DISTINCT ON (s.video_id)
            s.video_id,
            s.extracted_at,
            COUNT(s.id) OVER (PARTITION BY s.video_id) AS slide_count
        FROM stt_analysis.slides s
        WHERE s.video_id NOT IN (SELECT id FROM stt_analysis.videos)
        ORDER BY s.video_id, s.extracted_at DESC
    """)
    result = []
    for r in rows:
        vid_id = r["video_id"]
        result.append({
            "id": vid_id,
            "title": vid_id,
            "channel": None,
            "url": f"https://www.youtube.com/watch?v={vid_id}",
            "duration_sec": 0,
            "text_length": 0,
            "segments": 0,
            "language": None,
            "processed_at": r["extracted_at"].isoformat() if r.get("extracted_at") else None,
            "preview": f"슬라이드 {r['slide_count']}장 추출 완료 — STT 미처리",
            "thumbnail": f"https://img.youtube.com/vi/{vid_id}/mqdefault.jpg",
            "stt_status": "pending",
            "slide_count": r["slide_count"],
        })
    return result


@router.get("/slides/search")
async def search_slides(q: str = ""):
    """전체 슬라이드 OCR 텍스트 검색"""
    if not q.strip():
        return []
    rows = query(
        """
        SELECT s.video_id, v.title, s.slide_index, s.filename, s.time_str, s.ocr_text
        FROM stt_analysis.slides s
        LEFT JOIN stt_analysis.videos v ON v.id = s.video_id
        WHERE s.ocr_text ILIKE %s
        ORDER BY s.video_id, s.slide_index
        LIMIT 200
        """,
        (f"%{q}%",),
    )
    return [
        {
            "vid_id": r["video_id"],
            "title": r["title"] or r["video_id"],
            "slide_index": r["slide_index"],
            "filename": r["filename"],
            "time_str": r["time_str"],
            "ocr_text": r["ocr_text"] or "",
            "match_excerpt": _excerpt(r["ocr_text"] or "", q),
        }
        for r in rows
    ]


@router.get("/slides")
async def list_videos():
    """모든 영상 목록 + 슬라이드 수"""
    rows = query("""
        SELECT
            s.video_id,
            v.title,
            v.url,
            COUNT(s.id) AS total_slides,
            MAX(s.extracted_at) AS extracted_at,
            MIN(s.slide_index) AS first_idx
        FROM stt_analysis.slides s
        LEFT JOIN stt_analysis.videos v ON v.id = s.video_id
        GROUP BY s.video_id, v.title, v.url
        ORDER BY MAX(s.extracted_at) DESC
    """)
    return [
        {
            "vid_id": r["video_id"],
            "title": r["title"] or r["video_id"],
            "url": r["url"] or f"https://www.youtube.com/watch?v={r['video_id']}",
            "total_slides": r["total_slides"],
            "extracted_at": r["extracted_at"].isoformat() if r.get("extracted_at") else "",
            "thumbnail": f"/api/slides/{r['video_id']}/image/0" if r["total_slides"] > 0 else None,
        }
        for r in rows
    ]


@router.get("/slides/{vid_id}")
async def get_video_slides(vid_id: str):
    """특정 영상의 슬라이드 목록 (OCR 텍스트 포함, 이미지 제외)"""
    rows = query(
        """
        SELECT slide_index, filename, frame_time, time_str, ocr_text, llm_summary, extracted_at
        FROM stt_analysis.slides
        WHERE video_id = %s
        ORDER BY slide_index
        """,
        (vid_id,),
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Video not found")

    vid_rows = query(
        "SELECT title, url FROM stt_analysis.videos WHERE id = %s",
        (vid_id,),
    )
    title = vid_rows[0]["title"] if vid_rows else vid_id
    url = vid_rows[0]["url"] if vid_rows else f"https://www.youtube.com/watch?v={vid_id}"

    return {
        "video_id": vid_id,
        "title": title,
        "url": url,
        "total_slides": len(rows),
        "extracted_at": rows[0]["extracted_at"].isoformat() if rows and rows[0].get("extracted_at") else "",
        "slides": [
            {
                "slide_index": r["slide_index"],
                "timestamp": r["frame_time"],
                "time_str": r["time_str"],
                "filename": r["filename"],
                "ocr_text": r["ocr_text"] or "",
                "llm_summary": r["llm_summary"] or "",
            }
            for r in rows
        ],
    }


@router.get("/slides/{vid_id}/image/{filename}")
async def get_slide_image(vid_id: str, filename: str):
    """슬라이드 이미지를 DB에서 반환 (filename 또는 slide_index 모두 허용)"""
    if ".." in filename or "/" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    # filename이 숫자면 slide_index로 조회, 아니면 filename으로 조회
    if filename.isdigit():
        rows = query(
            "SELECT image_data FROM stt_analysis.slides WHERE video_id = %s AND slide_index = %s",
            (vid_id, int(filename)),
        )
    else:
        rows = query(
            "SELECT image_data FROM stt_analysis.slides WHERE video_id = %s AND filename = %s",
            (vid_id, filename),
        )
    if not rows or not rows[0]["image_data"]:
        raise HTTPException(status_code=404, detail="Image not found")
    return Response(content=bytes(rows[0]["image_data"]), media_type="image/jpeg")


@router.delete("/slides/{vid_id}/slide/{slide_index}")
async def delete_slide(vid_id: str, slide_index: int):
    """특정 슬라이드 DB에서 삭제"""
    from db import execute
    rows = query(
        "SELECT id FROM stt_analysis.slides WHERE video_id = %s AND slide_index = %s",
        (vid_id, slide_index),
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Slide not found")

    execute(
        "DELETE FROM stt_analysis.slides WHERE video_id = %s AND slide_index = %s",
        (vid_id, slide_index),
    )

    remaining = query(
        "SELECT COUNT(*) AS cnt FROM stt_analysis.slides WHERE video_id = %s",
        (vid_id,),
    )
    total = remaining[0]["cnt"] if remaining else 0

    execute(
        "UPDATE stt_analysis.videos SET slides_count = %s WHERE id = %s",
        (total, vid_id),
    )

    return {"ok": True, "total_slides": total}


def _excerpt(text: str, query_str: str, radius: int = 80) -> str:
    idx = text.lower().find(query_str.lower())
    if idx < 0:
        return text[:160]
    start = max(0, idx - radius)
    end = min(len(text), idx + len(query_str) + radius)
    return ("..." if start > 0 else "") + text[start:end] + ("..." if end < len(text) else "")
