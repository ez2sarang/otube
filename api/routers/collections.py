"""Collection(수집 그룹) 관련 API"""
import json
import re
import subprocess
import time

from fastapi import APIRouter
from pydantic import BaseModel

from db import execute, query, query_one
from services.task_manager import task_manager, TaskStatus

router = APIRouter(prefix="/api")


def load_collections():
    return query("SELECT * FROM stt_analysis.collections ORDER BY created_at DESC")


def save_collection(col):
    execute("""
        INSERT INTO stt_analysis.collections (id, type, name, source_url, channel, item_count, total_duration, total_chars, status, progress)
        VALUES (%(id)s, %(type)s, %(name)s, %(source_url)s, %(channel)s, %(item_count)s, %(total_duration)s, %(total_chars)s, %(status)s, %(progress)s)
        ON CONFLICT (id) DO UPDATE SET
            status = EXCLUDED.status, progress = EXCLUDED.progress,
            item_count = EXCLUDED.item_count, total_chars = EXCLUDED.total_chars
    """, col)


def save_video(video_data):
    execute("""
        INSERT INTO stt_analysis.videos (id, title, source, channel, url, duration_sec, text_length, segment_count, language, collection_id, thumbnail, preview, upload_date)
        VALUES (%(id)s, %(title)s, %(source)s, %(channel)s, %(url)s, %(duration_sec)s, %(text_length)s, %(segment_count)s, %(language)s, %(collection_id)s, %(thumbnail)s, %(preview)s, %(upload_date)s)
        ON CONFLICT (id) DO NOTHING
    """, video_data)


def save_transcript(video_id, raw_text, corrected_text, segments_json=None):
    execute("""
        INSERT INTO stt_analysis.transcripts (video_id, full_text, corrected_text, stt_source, correction_model, segments)
        VALUES (%s, %s, %s, 'vtt_llm', 'claude-haiku-4-5-20251001', %s)
        ON CONFLICT (video_id) DO UPDATE SET segments = EXCLUDED.segments
    """, (video_id, raw_text, corrected_text, segments_json))


class ProbeRequest(BaseModel):
    url: str


class BatchRequest(BaseModel):
    url: str
    collection_name: str = ""
    language: str = "ko"
    min_duration: int = 300  # 5분 이상만
    title_filter: str = ""  # 타이틀에 포함되어야 할 문자열 (빈 문자열이면 필터 없음)


@router.post("/probe")
async def probe_url(req: ProbeRequest):
    """URL을 분석해서 단건/다건 판별 + 영상 목록 반환"""
    url = req.url.strip()

    # URL 패턴으로 빠른 판별
    is_single = bool(re.search(r"(youtu\.be/|watch\?v=|shorts/)[a-zA-Z0-9_-]{11}", url))
    is_channel = bool(re.search(r"youtube\.com/@[^/]+", url))
    is_playlist = bool(re.search(r"playlist\?list=", url))

    if is_single and not is_channel and not is_playlist:
        # 단건: 제목만 가져오기
        try:
            result = subprocess.run(
                ["yt-dlp", "--cookies-from-browser", "chrome",
                 "--print", "%(id)s|%(title)s|%(duration)s|%(channel)s",
                 "--no-download", url],
                capture_output=True, text=True, timeout=30
            )
            parts = result.stdout.strip().split("|")
            if len(parts) >= 4:
                return {
                    "type": "single",
                    "url": url,
                    "channel": parts[3],
                    "videos": [{
                        "id": parts[0],
                        "title": parts[1],
                        "duration": float(parts[2]) if parts[2] else 0,
                    }],
                    "total": 1,
                }
        except Exception:
            pass
        return {"type": "unknown", "url": url, "error": "영상 정보를 가져올 수 없습니다.", "videos": [], "total": 0}

    # 다건: 플레이리스트/채널 스캔
    try:
        result = subprocess.run(
            ["yt-dlp", "--cookies-from-browser", "chrome", "--flat-playlist",
             "--print", "%(id)s|%(title)s|%(duration)s",
             url],
            capture_output=True, text=True, timeout=120
        )
        videos = []
        channel_name = ""
        for line in result.stdout.strip().split("\n"):
            parts = line.strip().split("|")
            if len(parts) >= 3:
                dur = float(parts[2]) if parts[2] and parts[2] != "NA" else 0
                videos.append({
                    "id": parts[0],
                    "title": parts[1],
                    "duration": dur,
                })

        # 채널 이름 추출
        if is_channel:
            m = re.search(r"@([^/]+)", url)
            channel_name = m.group(1) if m else ""

        url_type = "channel" if is_channel else "playlist"
        return {
            "type": url_type,
            "url": url,
            "channel": channel_name,
            "videos": videos,
            "total": len(videos),
            "long_form_count": sum(1 for v in videos if v["duration"] >= 300),
        }
    except Exception as e:
        return {"type": "unknown", "url": url, "error": str(e), "videos": [], "total": 0}


@router.post("/collections/create")
async def create_collection(req: BatchRequest):
    """Collection 생성 + 배치 VTT+LLM 처리 시작"""
    task_id = task_manager.create_task()

    def do_batch(task, url, collection_name, language, min_duration, title_filter):
        from concurrent.futures import ThreadPoolExecutor
        from vtt_pipeline import process_video_vtt

        # 1. probe
        task.update(TaskStatus.RUNNING, "영상 목록 스캔 중...", 5)
        probe_result = subprocess.run(
            ["yt-dlp", "--cookies-from-browser", "chrome", "--flat-playlist",
             "--print", "%(id)s|%(title)s|%(duration)s|%(upload_date)s",
             url],
            capture_output=True, text=True, timeout=300
        )

        videos = []
        for line in probe_result.stdout.strip().split("\n"):
            parts = line.strip().split("|")
            if len(parts) >= 3:
                dur = float(parts[2]) if parts[2] and parts[2] != "NA" else 0
                if dur >= min_duration:
                    if title_filter and title_filter not in parts[1]:
                        continue
                    raw_date = parts[3].strip() if len(parts) >= 4 else ""
                    ud = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:8]}" if raw_date and raw_date != "NA" and len(raw_date) == 8 else None
                    videos.append({"id": parts[0], "title": parts[1], "duration": dur, "upload_date": ud})

        if not videos:
            return {"error": "조건에 맞는 영상이 없습니다."}

        # 2. Collection 생성
        existing_cols = load_collections()
        col_id = f"col_{len(existing_cols)+1:03d}"
        channel_name = ""
        m = re.search(r"@([^/]+)", url)
        if m:
            channel_name = m.group(1)

        col = {
            "id": col_id,
            "type": "channel" if "@" in url else "playlist" if "playlist" in url else "batch",
            "name": collection_name or col_id,
            "source_url": url,
            "channel": channel_name,
            "item_count": len(videos),
            "total_duration": sum(v["duration"] for v in videos),
            "total_chars": 0,
            "status": "processing",
            "progress": 0,
        }
        save_collection(col)

        task.update(TaskStatus.RUNNING, f"{len(videos)}개 영상 처리 시작", 10)

        # 이미 처리된 video ID 조회
        existing_rows = query(
            "SELECT id FROM stt_analysis.videos WHERE collection_id = %s", (col_id,)
        )
        existing_ids = {row["id"] for row in existing_rows}
        done = 0

        def _process_vtt(vid_id):
            return process_video_vtt(
                vid_id,
                f"https://youtu.be/{vid_id}",
                language,
            )

        # 처리할 영상 필터링
        to_process = [v for v in videos if v["id"] not in existing_ids]
        task.update(TaskStatus.RUNNING, f"{len(to_process)}개 VTT 다운로드 시작 (5병렬)", 10)

        from concurrent.futures import as_completed

        def _save_result(v, vtt_result):
            """VTT 결과를 DB에 저장"""
            raw_text = vtt_result["raw_text"]
            segments = vtt_result.get("segments", [])
            segments_json = json.dumps(segments, ensure_ascii=False) if segments else None
            save_video({
                "id": v["id"],
                "title": v["title"],
                "source": "youtube",
                "channel": channel_name or "batch",
                "url": f"https://youtu.be/{v['id']}",
                "duration_sec": int(v["duration"]),
                "text_length": vtt_result["text_length"],
                "segment_count": 0,
                "language": language,
                "collection_id": col_id,
                "thumbnail": f"https://img.youtube.com/vi/{v['id']}/mqdefault.jpg",
                "preview": raw_text[:200] if raw_text else "",
                "upload_date": v.get("upload_date"),
            })
            save_transcript(v["id"], raw_text, vtt_result.get("corrected_text"), segments_json)

        with ThreadPoolExecutor(max_workers=5) as vtt_pool:
            # 모든 영상을 병렬로 제출
            future_to_video = {}
            for v in to_process:
                future = vtt_pool.submit(_process_vtt, v["id"])
                future_to_video[future] = v

            for future in as_completed(future_to_video):
                v = future_to_video[future]
                done += 1
                pct = 10 + int(85 * (done / len(to_process)))
                try:
                    vtt_result = future.result()
                    if vtt_result:
                        _save_result(v, vtt_result)
                        task.update(TaskStatus.RUNNING, f"[{done}/{len(to_process)}] {v['title'][:30]}", pct)
                    else:
                        task.update(TaskStatus.RUNNING, f"[{done}/{len(to_process)}] VTT 없음: {v['title'][:25]}", pct)
                except Exception as e:
                    task.update(TaskStatus.RUNNING, f"[{done}/{len(to_process)}] 오류: {str(e)[:40]}", pct)

        # 4. Collection 상태 업데이트
        total_chars = sum(
            row["text_length"]
            for row in query(
                "SELECT text_length FROM stt_analysis.videos WHERE collection_id = %s", (col_id,)
            )
        )
        col.update({
            "status": "done",
            "total_chars": total_chars,
            "item_count": done,
            "progress": 100,
        })
        save_collection(col)

        return {
            "collection_id": col_id,
            "name": col["name"],
            "done": done,
            "total": len(videos),
        }

    task_manager.run_in_background(
        task_id, do_batch,
        req.url, req.collection_name, req.language, req.min_duration, req.title_filter
    )
    return {"task_id": task_id}


@router.get("/collections")
async def list_collections():
    return load_collections()


@router.get("/videos")
async def list_videos(collection_id: str = None, channel: str = None, search: str = None):
    """DB에서 영상 목록 반환 (옵션: collection_id, channel, search 필터)"""
    conditions = []
    params = []
    if collection_id:
        conditions.append("v.collection_id = %s")
        params.append(collection_id)
    if channel:
        conditions.append("v.channel = %s")
        params.append(channel)
    if search:
        conditions.append("v.title ILIKE %s")
        params.append(f"%{search}%")

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    rows = query(f"""
        SELECT v.id, v.title, v.channel, v.url, v.duration_sec, v.text_length,
               v.segment_count, v.language, v.collection_id, v.thumbnail, v.preview,
               v.upload_date
        FROM stt_analysis.videos v
        {where}
        ORDER BY COALESCE(v.upload_date, CURRENT_DATE) DESC, v.id DESC
    """, params or None)
    return list(rows)


@router.get("/videos/summary")
async def videos_summary():
    """전체 요약 통계"""
    rows = query("""
        SELECT channel,
               COUNT(*) AS count,
               SUM(duration_sec) AS total_duration,
               SUM(text_length) AS total_chars
        FROM stt_analysis.videos
        GROUP BY channel
    """)
    channels = {
        r["channel"]: {
            "count": r["count"],
            "totalDuration": float(r["total_duration"] or 0),
            "totalChars": int(r["total_chars"] or 0),
        }
        for r in rows
    }
    totals_row = query_one("""
        SELECT COUNT(*) AS total,
               SUM(duration_sec) AS total_duration,
               SUM(text_length) AS total_chars
        FROM stt_analysis.videos
    """)
    return {
        "total": totals_row["total"] if totals_row else 0,
        "channels": channels,
        "totalDuration": float(totals_row["total_duration"] or 0) if totals_row else 0,
        "totalChars": int(totals_row["total_chars"] or 0) if totals_row else 0,
    }


class AskRequest(BaseModel):
    question: str
    history: list = []  # [{role: "user"|"assistant", content: str}]


class AskMultiRequest(BaseModel):
    video_ids: list
    question: str
    history: list = []


@router.post("/videos/ask-multi")
async def ask_videos_multi(req: AskMultiRequest):
    """여러 영상 트랜스크립트를 합쳐서 LLM에 질문 (SSE 스트리밍)"""
    import json
    from fastapi.responses import StreamingResponse as SR
    from llm_gateway import call_llm

    contexts = []
    for vid_id in req.video_ids[:5]:  # 최대 5개
        row = query_one(
            "SELECT corrected_text, full_text FROM stt_analysis.transcripts WHERE video_id = %s",
            (vid_id,)
        )
        transcript = (row["corrected_text"] or row["full_text"] or "") if row else ""
        video_row = query_one("SELECT title FROM stt_analysis.videos WHERE id = %s", (vid_id,))
        title = video_row["title"] if video_row else vid_id
        if transcript:
            # 각 영상당 최대 8000자
            contexts.append(f"[영상: {title}]\n{transcript[:8000]}")

    if not contexts:
        async def empty():
            yield 'data: {"error": "트랜스크립트를 찾을 수 없습니다."}\n\n'
        return SR(empty(), media_type="text/event-stream")

    combined = "\n\n---\n\n".join(contexts)
    task = f"""당신은 다음 YouTube 영상들의 트랜스크립트를 분석하는 전문가입니다.

{combined}

위 영상들의 트랜스크립트를 바탕으로 사용자의 질문에 정확하고 구체적으로 답하세요.
여러 영상에 걸친 공통점, 차이점, 종합적 인사이트도 제공하세요.
트랜스크립트에 없는 내용은 없다고 명확히 말하세요."""

    history_lines = [f"{h['role']}: {h['content']}" for h in req.history]
    text_input = "\n".join(history_lines + [f"user: {req.question}"]) if history_lines else req.question

    def stream_response():
        output = call_llm(task=task, text=text_input, model="haiku")
        if output is None:
            yield 'data: {"error": "LLM 처리 실패"}\n\n'
            return
        chunk_size = 50
        for i in range(0, len(output), chunk_size):
            yield f"data: {json.dumps({'text': output[i:i+chunk_size]})}\n\n"
        yield 'data: {"done": true}\n\n'

    return SR(
        stream_response(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/videos/{video_id}/ask")
async def ask_video(video_id: str, req: AskRequest):
    """트랜스크립트 컨텍스트로 LLM에게 질문 (SSE 스트리밍)"""
    import json
    from fastapi.responses import StreamingResponse as SR
    from llm_gateway import call_llm

    row = query_one(
        "SELECT corrected_text, full_text FROM stt_analysis.transcripts WHERE video_id = %s",
        (video_id,)
    )
    transcript = (row["corrected_text"] or row["full_text"] or "") if row else ""

    video_row = query_one("SELECT title FROM stt_analysis.videos WHERE id = %s", (video_id,))
    title = video_row["title"] if video_row else video_id

    task = f"""당신은 다음 YouTube 영상의 트랜스크립트를 분석하는 전문가입니다.

영상 제목: {title}

트랜스크립트:
{transcript[:30000]}

트랜스크립트를 바탕으로 사용자의 질문에 정확하고 구체적으로 답하세요.
트랜스크립트에 없는 내용은 없다고 명확히 말하세요."""

    history_lines = [f"{h['role']}: {h['content']}" for h in req.history]
    text_input = "\n".join(history_lines + [f"user: {req.question}"]) if history_lines else req.question

    def stream_response():
        output = call_llm(task=task, text=text_input, model="haiku")
        if output is None:
            yield "data: {\"error\": \"LLM 처리 실패\"}\n\n"
            return
        chunk_size = 50
        for i in range(0, len(output), chunk_size):
            yield f"data: {json.dumps({'text': output[i:i+chunk_size]})}\n\n"
        yield "data: {\"done\": true}\n\n"

    return SR(
        stream_response(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/videos/{video_id}/transcript")
async def get_transcript(video_id: str):
    """영상 트랜스크립트 반환"""
    row = query_one(
        "SELECT full_text, corrected_text, segments FROM stt_analysis.transcripts WHERE video_id = %s",
        (video_id,)
    )
    if not row:
        return {"fullText": "", "correctedText": "", "segments": []}

    segs = []
    if row.get("segments"):
        try:
            segs = json.loads(row["segments"]) if isinstance(row["segments"], str) else row["segments"]
        except Exception:
            segs = []

    full_text = row["full_text"] or ""
    corrected = row["corrected_text"] or ""
    # 교정 텍스트가 원본의 10% 미만이면 오류로 간주하고 원본 사용
    if corrected and len(full_text) > 0 and len(corrected) < len(full_text) * 0.1:
        corrected = ""

    return {
        "fullText": corrected or full_text,
        "correctedText": corrected,
        "segments": segs,
    }


@router.post("/videos/{video_id}/reprocess-segments")
async def reprocess_segments(video_id: str):
    """기존 영상의 세그먼트를 재추출해서 DB 저장"""
    from vtt_pipeline import download_vtt, parse_vtt_with_segments

    video = query_one("SELECT url, language FROM stt_analysis.videos WHERE id = %s", (video_id,))
    if not video:
        return {"error": "영상을 찾을 수 없습니다."}

    vtt_content = download_vtt(video["url"], video.get("language") or "ko")
    if not vtt_content:
        return {"error": "VTT를 다운로드할 수 없습니다."}

    segments = parse_vtt_with_segments(vtt_content)
    segments_json = json.dumps(segments, ensure_ascii=False) if segments else None

    execute(
        "UPDATE stt_analysis.transcripts SET segments = %s WHERE video_id = %s",
        (segments_json, video_id)
    )
    return {"video_id": video_id, "segments_count": len(segments)}


@router.post("/videos/reprocess-all-segments")
async def reprocess_all_segments():
    """세그먼트가 없는 모든 영상을 백그라운드에서 재처리"""
    task_id = task_manager.create_task()

    def do_reprocess(task):
        from concurrent.futures import ThreadPoolExecutor, as_completed
        from vtt_pipeline import download_vtt, parse_vtt_with_segments
        import threading

        videos = query("""
            SELECT v.id, v.url, v.language, v.title
            FROM stt_analysis.videos v
            JOIN stt_analysis.transcripts t ON v.id = t.video_id
            WHERE t.segments IS NULL
        """)

        if not videos:
            return {"message": "모든 영상에 세그먼트가 있습니다.", "count": 0}

        total = len(videos)
        done = 0
        failed = 0
        lock = threading.Lock()

        def _process(v):
            try:
                vtt_content = download_vtt(v["url"], v.get("language") or "ko")
                if not vtt_content:
                    return False
                segments = parse_vtt_with_segments(vtt_content)
                segments_json = json.dumps(segments, ensure_ascii=False) if segments else "[]"
                execute(
                    "UPDATE stt_analysis.transcripts SET segments = %s WHERE video_id = %s",
                    (segments_json, v["id"])
                )
                return True
            except Exception:
                return False

        task.update(TaskStatus.RUNNING, f"세그먼트 재추출 시작 ({total}개, 5병렬)", 1)

        with ThreadPoolExecutor(max_workers=5) as pool:
            future_to_vid = {pool.submit(_process, v): v for v in videos}
            for future in as_completed(future_to_vid):
                v = future_to_vid[future]
                with lock:
                    if future.result():
                        done += 1
                    else:
                        failed += 1
                    completed = done + failed
                    pct = int(100 * completed / total)
                task.update(TaskStatus.RUNNING, f"[{completed}/{total}] {v['title'][:28]} ✓{done} ✗{failed}", pct)

        return {"done": done, "failed": failed, "total": total}

    task_manager.run_in_background(task_id, do_reprocess)
    return {"task_id": task_id}
