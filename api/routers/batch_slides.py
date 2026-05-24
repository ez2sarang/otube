"""배치 슬라이드 추출 파이프라인 모니터링"""
import json
import subprocess
import asyncio
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/api")

SLIDES_DIR = Path(__file__).parent.parent.parent / "data" / "slides"
LOG_FILE = Path("/tmp/slides-vision.log")


def is_batch_running() -> bool:
    """배치 프로세스 실행 중 확인"""
    try:
        result = subprocess.run(
            ["pgrep", "-f", "batch_slides_playlist"],
            capture_output=True,
            timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False


def parse_failed_videos(log_content: str) -> set:
    """로그에서 실패한 비디오 ID 추출"""
    import re
    failed = set()
    for line in log_content.split("\n"):
        if "FAIL:" in line:
            # Format: "FAIL: 다운로드 실패: ERROR: [youtube] <vid_id>: ..."
            m = re.search(r'\[youtube\]\s+([A-Za-z0-9_-]{11}):', line)
            if m:
                failed.add(m.group(1))
    return failed


def get_batch_status() -> Dict[str, Any]:
    """배치 상태 스냅샷"""
    status = {
        "running": is_batch_running(),
        "total": 0,
        "done": 0,
        "failed": 0,
        "in_progress": 0,
        "pending": 0,
        "total_slides": 0,
        "log_tail": [],
        "videos": []
    }

    # 로그 파일 읽기
    log_content = ""
    if LOG_FILE.exists():
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                log_content = f.read()
            lines = log_content.split("\n")
            status["log_tail"] = [l for l in lines[-8:] if l.strip()]
        except Exception:
            pass

    # 실패 비디오 ID 추출
    failed_ids = parse_failed_videos(log_content)

    # 슬라이드 디렉토리 스캔
    if SLIDES_DIR.exists():
        video_dirs = sorted([d for d in SLIDES_DIR.iterdir() if d.is_dir()])
        status["total"] = len(video_dirs)

        for vid_dir in video_dirs:
            vid_id = vid_dir.name
            meta_file = vid_dir / "meta.json"
            meta = {}
            slides = 0
            is_done = False

            # meta.json 확인
            if meta_file.exists():
                try:
                    with open(meta_file, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                    is_done = True
                    status["done"] += 1
                except Exception:
                    pass

            # 슬라이드 개수 세기
            slides = len(list(vid_dir.glob("slide_*.jpg")))
            status["total_slides"] += slides

            # 상태 결정
            if vid_id in failed_ids:
                state = "failed"
                status["failed"] += 1
            elif is_done:
                state = "done"
            elif slides > 0:
                state = "in_progress"
                status["in_progress"] += 1
            else:
                state = "pending"
                status["pending"] += 1

            # 제목 결정
            title = meta.get("title", vid_id)
            if not title or title == vid_id:
                title = vid_id

            status["videos"].append({
                "vid_id": vid_id,
                "title": title,
                "status": state,
                "slides": slides
            })

    return status


@router.get("/batch-slides/status")
async def get_status():
    """배치 상태 스냅샷 반환"""
    return get_batch_status()


@router.get("/batch-slides/stream")
async def stream_status():
    """SSE: 3초마다 상태 업데이트"""
    async def event_generator():
        last_status = None
        consecutive_idle = 0
        max_idle_count = 5  # 약 15초 동안 변화 없으면 중단

        while True:
            try:
                current_status = get_batch_status()

                # 상태 변경 또는 아직 실행 중이면 이벤트 발송
                if current_status != last_status or current_status["running"]:
                    data = json.dumps(current_status, ensure_ascii=False)
                    yield f"data: {data}\n\n"
                    last_status = current_status
                    consecutive_idle = 0
                else:
                    consecutive_idle += 1

                # 완료 조건: 실행 중 아님 + 모든 디렉토리에 meta.json 존재
                all_done = not current_status["running"]
                if all_done and SLIDES_DIR.exists():
                    all_have_meta = all(
                        (d / "meta.json").exists()
                        for d in SLIDES_DIR.iterdir()
                        if d.is_dir()
                    )
                    if all_have_meta or consecutive_idle >= max_idle_count:
                        yield f"data: {json.dumps(current_status, ensure_ascii=False)}\n\n"
                        break

                await asyncio.sleep(3)

            except Exception as e:
                print(f"[batch_slides stream error] {e}")
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )
