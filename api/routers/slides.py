"""슬라이드 뷰어 API"""
import json
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from db import query

router = APIRouter(prefix="/api")

SLIDES_DIR = Path(__file__).parent.parent.parent / "data" / "slides"


def _load_meta(vid_id: str) -> dict:
    meta_file = SLIDES_DIR / vid_id / "meta.json"
    if not meta_file.exists():
        raise HTTPException(status_code=404, detail="Video not found")
    with open(meta_file, encoding="utf-8") as f:
        return json.load(f)


@router.get("/slides-unprocessed")
async def list_slides_unprocessed():
    """STT DB에 없는 슬라이드 전용 영상 목록 (HistoryItem 호환 형식)"""
    try:
        rows = query("SELECT id FROM stt_analysis.videos")
        processed_ids = {r["id"] for r in rows}
    except Exception:
        processed_ids = set()

    result = []
    if not SLIDES_DIR.exists():
        return result

    for d in sorted(SLIDES_DIR.iterdir()):
        if not d.is_dir():
            continue
        vid_id = d.name
        if vid_id in processed_ids:
            continue
        meta_file = d / "meta.json"
        if not meta_file.exists():
            continue
        try:
            with open(meta_file, encoding="utf-8") as f:
                meta = json.load(f)
            first_slide = meta["slides"][0]["filename"] if meta.get("slides") else None
            result.append({
                "id": vid_id,
                "title": meta.get("title", vid_id),
                "channel": None,
                "url": meta.get("url", f"https://www.youtube.com/watch?v={vid_id}"),
                "duration_sec": 0,
                "text_length": 0,
                "segments": 0,
                "language": None,
                "processed_at": meta.get("extracted_at"),
                "preview": f"슬라이드 {meta.get('total_slides', 0)}장 추출 완료 — STT 미처리",
                "thumbnail": f"https://img.youtube.com/vi/{vid_id}/mqdefault.jpg",
                "stt_status": "pending",
                "slide_count": meta.get("total_slides", 0),
            })
        except Exception:
            continue
    return result


@router.get("/slides/search")
async def search_slides(q: str = ""):
    """전체 슬라이드 OCR 텍스트 검색 (무료, 로컬)"""
    if not q.strip():
        return []
    q_lower = q.lower()
    results = []
    if not SLIDES_DIR.exists():
        return results
    for d in sorted(SLIDES_DIR.iterdir()):
        if not d.is_dir():
            continue
        meta_file = d / "meta.json"
        if not meta_file.exists():
            continue
        try:
            with open(meta_file, encoding="utf-8") as f:
                meta = json.load(f)
            for slide in meta.get("slides", []):
                ocr = slide.get("ocr_text", "")
                if q_lower in ocr.lower():
                    results.append({
                        "vid_id": meta.get("video_id", d.name),
                        "title": meta.get("title", d.name),
                        "slide_index": slide["slide_index"],
                        "filename": slide["filename"],
                        "time_str": slide["time_str"],
                        "ocr_text": ocr,
                        "match_excerpt": _excerpt(ocr, q_lower),
                    })
        except Exception:
            continue
    return results


@router.get("/slides")
async def list_videos():
    """모든 영상 목록 + 슬라이드 수"""
    if not SLIDES_DIR.exists():
        return []
    result = []
    for d in sorted(SLIDES_DIR.iterdir()):
        if not d.is_dir():
            continue
        meta_file = d / "meta.json"
        if not meta_file.exists():
            continue
        try:
            with open(meta_file, encoding="utf-8") as f:
                meta = json.load(f)
            result.append({
                "vid_id": meta.get("video_id", d.name),
                "title": meta.get("title", d.name),
                "url": meta.get("url", ""),
                "total_slides": meta.get("total_slides", 0),
                "extracted_at": meta.get("extracted_at", ""),
                "thumbnail": meta["slides"][0]["filename"] if meta.get("slides") else None,
            })
        except Exception:
            continue
    return result


@router.get("/slides/{vid_id}")
async def get_video_slides(vid_id: str):
    """특정 영상의 슬라이드 목록 (OCR 텍스트 포함)"""
    return _load_meta(vid_id)


@router.get("/slides/{vid_id}/image/{filename}")
async def get_slide_image(vid_id: str, filename: str):
    """슬라이드 이미지 파일 서빙"""
    # 경로 순회 방지
    if ".." in filename or "/" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    img_path = SLIDES_DIR / vid_id / filename
    if not img_path.exists() or img_path.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(img_path, media_type="image/jpeg")


@router.delete("/slides/{vid_id}/slide/{slide_index}")
async def delete_slide(vid_id: str, slide_index: int):
    """특정 슬라이드 삭제: JPG 파일 제거 + meta.json 갱신"""
    meta = _load_meta(vid_id)
    slides = meta.get("slides", [])

    target = next((s for s in slides if s["slide_index"] == slide_index), None)
    if target is None:
        raise HTTPException(status_code=404, detail="Slide not found")

    # 파일 삭제
    img_path = SLIDES_DIR / vid_id / target["filename"]
    if img_path.exists():
        img_path.unlink()

    # meta.json 갱신
    meta["slides"] = [s for s in slides if s["slide_index"] != slide_index]
    meta["total_slides"] = len(meta["slides"])

    meta_file = SLIDES_DIR / vid_id / "meta.json"
    with open(meta_file, "w", encoding="utf-8") as f:
        import json as _json
        _json.dump(meta, f, ensure_ascii=False, indent=2)

    return {"ok": True, "total_slides": meta["total_slides"]}


def _excerpt(text: str, query: str, radius: int = 80) -> str:
    idx = text.lower().find(query)
    if idx < 0:
        return text[:160]
    start = max(0, idx - radius)
    end = min(len(text), idx + len(query) + radius)
    return ("..." if start > 0 else "") + text[start:end] + ("..." if end < len(text) else "")
