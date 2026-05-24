"""FastAPI 백엔드 메인"""
import glob
import os
import shutil
import sys
import time
import threading

sys.path.insert(0, os.path.dirname(__file__))

# .env 파일에서 환경변수 로드 (python-dotenv 없이)
_env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(_env_path):
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

import llm_gateway
from routers import stt, collections, share, tasks, batch_slides, slides, qa, playlists, search
from services.task_manager import task_manager

app = FastAPI(title="Offline Thinking API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3204", "http://localhost:3400"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(stt.router)
app.include_router(collections.router)
app.include_router(share.router)
app.include_router(tasks.router)
app.include_router(batch_slides.router)
app.include_router(slides.router)
app.include_router(qa.router)
app.include_router(playlists.router)
app.include_router(search.router)


# --- 임시 파일 자동 정리 ---

TEMP_DIRS = ["/tmp/stt-work", "/tmp/mind_mingle"]
CLEANUP_MAX_AGE_HOURS = 48  # 2일

def cleanup_old_temp_files():
    """TEMP_DIRS 안에서 48시간 이상 된 파일/디렉토리 삭제"""
    now = time.time()
    max_age_sec = CLEANUP_MAX_AGE_HOURS * 3600
    total_freed = 0

    for base_dir in TEMP_DIRS:
        if not os.path.exists(base_dir):
            continue

        for entry in os.listdir(base_dir):
            full_path = os.path.join(base_dir, entry)
            try:
                mtime = os.path.getmtime(full_path)
                age = now - mtime

                if age > max_age_sec:
                    if os.path.isdir(full_path):
                        size = sum(
                            os.path.getsize(os.path.join(dp, f))
                            for dp, _, fns in os.walk(full_path)
                            for f in fns
                        )
                        shutil.rmtree(full_path, ignore_errors=True)
                    else:
                        size = os.path.getsize(full_path)
                        os.remove(full_path)
                    total_freed += size
            except (OSError, PermissionError):
                continue

    if total_freed > 0:
        print(f"[cleanup] {total_freed / 1024 / 1024:.1f}MB 임시 파일 정리 완료 (>{CLEANUP_MAX_AGE_HOURS}시간)")


def periodic_cleanup(interval_hours=6):
    """백그라운드 스레드: 주기적으로 임시 파일 정리"""
    while True:
        time.sleep(interval_hours * 3600)
        try:
            cleanup_old_temp_files()
        except Exception:
            pass


@app.on_event("startup")
async def startup_cleanup():
    """서버 시작 시 오래된 임시 파일 정리 + 주기적 정리 스레드 시작"""
    cleanup_old_temp_files()
    thread = threading.Thread(target=periodic_cleanup, daemon=True)
    thread.start()


# --- API 엔드포인트 ---

@app.get("/api/tasks/{task_id}/events")
async def task_events(task_id: str):
    return StreamingResponse(
        task_manager.stream_events(task_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@app.post("/internal/llm-callback/{request_id}")
async def llm_callback(request_id: str, request: Request):
    """plugin-llm-gateway 콜백 수신 엔드포인트"""
    data = await request.json()
    llm_gateway.handle_callback(request_id, data)
    return {"ok": True}


@app.post("/internal/recorrect/{video_id}")
async def recorrect_transcript(video_id: str):
    """특정 영상의 corrected_text를 최신 프롬프트로 재교정"""
    import asyncio
    from vtt_pipeline import correct_with_llm
    from db import query, execute
    rows = query("SELECT full_text FROM stt_analysis.transcripts WHERE video_id = %s", (video_id,))
    if not rows:
        return {"error": "not found", "video_id": video_id}
    raw = rows[0]["full_text"]
    if not raw:
        return {"error": "empty full_text", "video_id": video_id}
    loop = asyncio.get_event_loop()
    corrected = await loop.run_in_executor(None, correct_with_llm, raw)
    if not corrected or corrected == raw:
        return {"skipped": True, "video_id": video_id, "reason": "no change or gateway error"}
    execute(
        "UPDATE stt_analysis.transcripts SET corrected_text = %s, correction_model = 'claude-haiku-4-5-20251001' WHERE video_id = %s",
        (corrected, video_id),
    )
    return {"ok": True, "video_id": video_id, "chars": len(corrected)}


@app.get("/api/health")
async def health():
    """헬스체크 + 임시 파일 용량 정보"""
    temp_size = 0
    for base_dir in TEMP_DIRS:
        if os.path.exists(base_dir):
            for dp, _, fns in os.walk(base_dir):
                for f in fns:
                    try:
                        temp_size += os.path.getsize(os.path.join(dp, f))
                    except OSError:
                        pass

    return {
        "status": "ok",
        "temp_usage_mb": round(temp_size / 1024 / 1024, 1),
        "cleanup_policy": f"{CLEANUP_MAX_AGE_HOURS}시간 후 자동 삭제",
    }


@app.post("/api/cleanup")
async def manual_cleanup():
    """수동 임시 파일 정리"""
    cleanup_old_temp_files()

    # 현재 남은 용량 계산
    remaining = 0
    for base_dir in TEMP_DIRS:
        if os.path.exists(base_dir):
            for dp, _, fns in os.walk(base_dir):
                for f in fns:
                    try:
                        remaining += os.path.getsize(os.path.join(dp, f))
                    except OSError:
                        pass

    return {
        "message": "정리 완료",
        "remaining_mb": round(remaining / 1024 / 1024, 1),
    }


@app.post("/api/cleanup/force")
async def force_cleanup():
    """모든 임시 파일 강제 삭제"""
    freed = 0
    for base_dir in TEMP_DIRS:
        if os.path.exists(base_dir):
            for dp, _, fns in os.walk(base_dir):
                for f in fns:
                    try:
                        freed += os.path.getsize(os.path.join(dp, f))
                    except OSError:
                        pass
            shutil.rmtree(base_dir, ignore_errors=True)

    return {
        "message": "모든 임시 파일 삭제 완료",
        "freed_mb": round(freed / 1024 / 1024, 1),
    }


if __name__ == "__main__":
    import uvicorn
    print("\n=== Offline Thinking API ===")
    print("  http://localhost:9102")
    print("  http://localhost:9102/docs")
    print(f"  임시 파일: {CLEANUP_MAX_AGE_HOURS}시간 후 자동 삭제")
    print("===========================\n")
    uvicorn.run(app, host="0.0.0.0", port=9102)
