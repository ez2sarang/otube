"""STT 관련 API 라우터"""
import json
import os
import re
import subprocess
import tempfile
import time

from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from services.task_manager import task_manager, TaskStatus

router = APIRouter(prefix="/api")


class YoutubeRequest(BaseModel):
    url: str
    language: str = "ko"


@router.post("/transcribe/youtube")
async def transcribe_youtube(req: YoutubeRequest):
    task_id = task_manager.create_task()

    def do_transcribe(task, url, language):
        from vtt_pipeline import process_video_vtt
        from db import execute, query

        task.update(TaskStatus.RUNNING, "메타데이터 가져오는 중...", 5)

        # 제목 + 채널 + 길이 가져오기
        title = url
        channel_name = "youtube"
        duration_sec = 0
        upload_date = None
        try:
            cdp_profile = "/tmp/chrome-cdp-gdrive"
            cookie_args = ["--cookies-from-browser", f"chrome:{cdp_profile}"] if os.path.exists(cdp_profile) else ["--cookies-from-browser", "chrome"]
            meta_result = subprocess.run(
                ["yt-dlp"] + cookie_args + [
                 "--print", "%(title)s|%(channel)s|%(duration)s|%(upload_date)s", "--no-download", url],
                capture_output=True, text=True, timeout=30,
            )
            if meta_result.returncode == 0:
                parts = meta_result.stdout.strip().split("|")
                if len(parts) >= 1 and parts[0].strip():
                    title = parts[0].strip()
                if len(parts) >= 2 and parts[1].strip():
                    channel_name = parts[1].strip()
                if len(parts) >= 3 and parts[2].strip():
                    duration_sec = int(float(parts[2].strip()))
                if len(parts) >= 4 and parts[3].strip() and parts[3].strip() != "NA":
                    d = parts[3].strip()
                    upload_date = f"{d[:4]}-{d[4:6]}-{d[6:8]}"
        except Exception:
            pass

        # video ID 추출
        vid_match = re.search(r"(?:youtu\.be/|v=|embed/)([a-zA-Z0-9_-]{11})", url)
        vid = vid_match.group(1) if vid_match else task_id

        task.update(TaskStatus.RUNNING, f"VTT 자막 다운로드 중: {title}", 20)
        task.update(TaskStatus.RUNNING, "자막 보정 + OCR 프레임 분석 중...", 40)
        vtt_result = process_video_vtt(vid, url, language, use_ocr=True)

        stt_source = "vtt_llm"
        correction_model = "claude-haiku-4-5-20251001"

        if vtt_result:
            raw_text = vtt_result["raw_text"]
            corrected_text = vtt_result.get("corrected_text") or raw_text
            ocr_result = vtt_result.get("ocr")
            segments = vtt_result.get("segments", [])
        else:
            # VTT 없음 → Whisper 폴백
            task.update(TaskStatus.RUNNING, "자막 없음 — Whisper로 오디오 변환 중...", 50)
            try:
                from transcribe import download_audio, transcribe_audio
                audio_dir = f"/tmp/stt-work/{vid}"
                audio_path = download_audio(url, audio_dir)
                whisper_result = transcribe_audio(audio_path, language)
                raw_text = whisper_result.get("text", "").strip()
                corrected_text = raw_text
                ocr_result = None
                stt_source = "whisper"
                correction_model = None

                # Whisper 세그먼트를 VTT 세그먼트 포맷으로 변환
                segments = []
                for seg in whisper_result.get("segments", []):
                    t = seg.get("start", 0)
                    hh = int(t // 3600)
                    mm = int((t % 3600) // 60)
                    ss = int(t % 60)
                    time_str = f"{hh}:{mm:02d}:{ss:02d}" if hh > 0 else f"{mm}:{ss:02d}"
                    segments.append({
                        "time_str": time_str,
                        "start_sec": t,
                        "text": seg.get("text", "").strip(),
                    })

                import shutil
                shutil.rmtree(audio_dir, ignore_errors=True)

                if not raw_text:
                    return {"error": "VTT 자막도 없고 Whisper 변환도 실패했습니다."}
            except Exception as e:
                return {"error": f"Whisper 폴백 실패: {str(e)[:120]}"}

        task.update(TaskStatus.RUNNING, "DB 저장 중...", 90)

        ocr_text = ocr_result["text"] if ocr_result else None
        segments_json = json.dumps(segments, ensure_ascii=False) if segments else None

        # videos 테이블에 저장
        execute("""
            INSERT INTO stt_analysis.videos (id, title, source, channel, url, duration_sec, text_length, segment_count, language, thumbnail, preview, upload_date)
            VALUES (%s, %s, 'youtube', %s, %s, %s, %s, 0, %s, %s, %s, %s)
            ON CONFLICT (id) DO NOTHING
        """, (
            vid, title, channel_name, url, duration_sec,
            len(corrected_text), language,
            f"https://img.youtube.com/vi/{vid}/mqdefault.jpg",
            corrected_text[:200],
            upload_date,
        ))

        # transcripts 테이블에 저장
        execute("""
            INSERT INTO stt_analysis.transcripts (video_id, full_text, corrected_text, stt_source, correction_model, segments)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (video_id) DO UPDATE SET segments = EXCLUDED.segments
        """, (vid, raw_text, corrected_text, stt_source, correction_model, segments_json))

        # OCR 결과 저장 (ocr_text 컬럼이 있을 때만)
        if ocr_text:
            try:
                execute("""
                    UPDATE stt_analysis.transcripts
                    SET ocr_text = %s,
                        ocr_frames_total = %s,
                        ocr_frames_unique = %s
                    WHERE video_id = %s
                """, (
                    ocr_text,
                    ocr_result.get("frames_total", 0),
                    ocr_result.get("frames_unique", 0),
                    vid,
                ))
            except Exception:
                pass  # 컬럼 미존재 시 무시

        # 슬라이드 추출 (STT 완료 후 자동 실행)
        task.update(TaskStatus.RUNNING, "슬라이드 추출 중 (영상 다운로드)...", 93)
        slides_count = 0
        slides_error = None
        try:
            from batch_slides_playlist import process_video
            task.update(TaskStatus.RUNNING, "슬라이드 추출 중 (장면 감지)...", 95)
            slide_result = process_video({"id": vid, "title": title, "url": url})
            if slide_result.get("status") == "ok":
                slides_count = slide_result.get("slides", 0)
            elif slide_result.get("status") == "error":
                slides_error = slide_result.get("error", "알 수 없는 오류")
                print(f"[slides] {vid} 슬라이드 추출 실패: {slides_error}")
        except Exception as e:
            slides_error = str(e)[:120]
            print(f"[slides] {vid} 슬라이드 추출 예외: {slides_error}")

        return {
            "title": title,
            "text": corrected_text,
            "segments": len(segments),
            "ocr_frames": ocr_result.get("frames_unique", 0) if ocr_result else 0,
            "stt_source": stt_source,
            "video_id": vid,
            "slides": slides_count,
            **({"slides_error": slides_error} if slides_error else {}),
        }

    task_manager.run_in_background(task_id, do_transcribe, req.url, req.language)
    return {"task_id": task_id}


@router.post("/transcribe/file")
async def transcribe_file(
    file: UploadFile = File(...),
    language: str = Form("ko"),
    model: str = Form("mlx-community/whisper-large-v3-turbo"),
):
    task_id = task_manager.create_task()

    # 임시 파일에 저장
    suffix = os.path.splitext(file.filename or ".wav")[1]
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    content = await file.read()
    tmp.write(content)
    tmp.close()
    tmp_path = tmp.name

    def do_transcribe(task, audio_path, lang, mdl, filename):
        from transcribe import transcribe_audio, format_transcript_md, format_transcript_srt

        task.update(TaskStatus.RUNNING, "STT 변환 중...", 30)
        start = time.time()
        result = transcribe_audio(audio_path, lang, mdl)
        elapsed = time.time() - start

        task.update(TaskStatus.RUNNING, "문서 생성 중...", 90)
        md_text = format_transcript_md(result, filename)
        srt_text = format_transcript_srt(result)

        os.unlink(audio_path)

        return {
            "markdown": md_text,
            "srt": srt_text,
            "text": result.get("text", ""),
            "segments": len(result.get("segments", [])),
            "elapsed": elapsed,
        }

    task_manager.run_in_background(task_id, do_transcribe, tmp_path, language, model, file.filename)
    return {"task_id": task_id}
