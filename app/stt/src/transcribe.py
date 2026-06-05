"""STT 변환 핵심 로직"""
import glob
import json
import math
import os
import subprocess
import tempfile
import time
import urllib.request
import urllib.error
import uuid
from pathlib import Path
from typing import Optional

LLM_GATEWAY_BASE = os.environ.get("LLM_GATEWAY_BASE", "http://localhost:3100")
LLM_GATEWAY_WEBHOOK = f"{LLM_GATEWAY_BASE}/api/plugins/llm-gateway/webhooks/process"
LLM_GATEWAY_GET_JOB = f"{LLM_GATEWAY_BASE}/api/plugins/llm-gateway/data/get-job"

CORRECTION_TASK = (
    "다음 한국어 STT(음성 인식) 텍스트의 발음 오류, 맞춤법, 문장 부호, 어색한 표현을 교정하세요. "
    "원본의 의미를 최대한 보존하고, 교정된 텍스트만 출력하세요."
)

MAX_CHUNK_CHARS = 35_000  # LLM Gateway 40k 제한보다 여유 있게


def _submit_correction_job(text: str, task: str, timeout: int) -> str:
    """단일 청크를 LLM Gateway에 제출하고 결과를 반환합니다."""
    request_id = str(uuid.uuid4())
    payload = json.dumps({
        "requestId": request_id,
        "model": "haiku",
        "task": task,
        "text": text,
        "think": False,
    }).encode("utf-8")
    req = urllib.request.Request(
        LLM_GATEWAY_WEBHOOK,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
    except Exception as e:
        raise RuntimeError(f"LLM Gateway 요청 실패 ({LLM_GATEWAY_WEBHOOK}): {e}")

    if result.get("status") != "success":
        raise RuntimeError(f"LLM Gateway 제출 실패: {result}")

    poll_payload = json.dumps({"params": {"requestId": request_id}}).encode("utf-8")
    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(3)
        poll_req = urllib.request.Request(
            LLM_GATEWAY_GET_JOB,
            data=poll_payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(poll_req, timeout=10) as resp:
                poll_result = json.loads(resp.read())
        except Exception:
            continue

        job = poll_result.get("data") or {}
        status = job.get("status")
        if status == "completed":
            inner = job.get("data") or {}
            return inner.get("output", "")
        elif status == "error":
            inner = job.get("data") or {}
            raise RuntimeError(f"교정 오류: {inner.get('error', '알 수 없는 오류')}")

    raise RuntimeError(f"교정 타임아웃 ({timeout}초)")


def _split_into_chunks(text: str, max_chars: int = MAX_CHUNK_CHARS) -> list:
    """텍스트를 max_chars 이하의 청크로 분할합니다. 문장 단위로 자릅니다."""
    if len(text) <= max_chars:
        return [text]

    chunks = []
    current = []
    current_len = 0

    # 공백으로 분리된 단어/문장 단위로 처리
    sentences = text.split(" ")
    for word in sentences:
        word_len = len(word) + 1  # 공백 포함
        if current_len + word_len > max_chars and current:
            chunks.append(" ".join(current))
            current = [word]
            current_len = word_len
        else:
            current.append(word)
            current_len += word_len

    if current:
        chunks.append(" ".join(current))

    return chunks


def correct_text(text: str, language: str = "ko", timeout: int = 180) -> str:
    """Paperclip LLM Gateway(3100)를 통한 STT 텍스트 교정.

    긴 텍스트는 35k자 단위로 자동 청크 분할 후 순차 교정합니다.
    """
    task = CORRECTION_TASK if language == "ko" else f"Correct this {language} STT transcript. Output only the corrected text."

    chunks = _split_into_chunks(text)
    if len(chunks) == 1:
        return _submit_correction_job(text, task, timeout)

    corrected_chunks = []
    for i, chunk in enumerate(chunks):
        corrected_chunks.append(_submit_correction_job(chunk, task, timeout))

    return " ".join(corrected_chunks)


def download_audio(url: str, output_dir: str = "/tmp/stt-work") -> str:
    """YouTube URL에서 오디오를 WAV로 다운로드"""
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "audio.wav")

    # 기존 파일 제거
    if os.path.exists(output_path):
        os.remove(output_path)

    result = subprocess.run(
        ["yt-dlp", "-x", "--audio-format", "wav", "--audio-quality", "0",
         "-o", os.path.join(output_dir, "audio.%(ext)s"), url],
        capture_output=True, text=True, timeout=300
    )
    if result.returncode != 0:
        raise RuntimeError(f"다운로드 실패: {result.stderr}")

    if not os.path.exists(output_path):
        raise FileNotFoundError(f"오디오 파일이 생성되지 않았습니다: {output_path}")

    return output_path


def get_video_title(url: str) -> str:
    """YouTube 영상 제목 가져오기"""
    try:
        result = subprocess.run(
            ["yt-dlp", "--print", "title", url],
            capture_output=True, text=True, timeout=30
        )
        return result.stdout.strip() if result.returncode == 0 else "Unknown"
    except Exception:
        return "Unknown"


def transcribe_audio(
    audio_path: str,
    language: str = "ko",
    model: str = "mlx-community/whisper-large-v3-turbo"
) -> dict:
    """mlx-whisper로 오디오를 텍스트로 변환"""
    import mlx_whisper

    result = mlx_whisper.transcribe(
        audio_path,
        path_or_hf_repo=model,
        language=language,
        verbose=False
    )
    return result


def format_transcript_md(result: dict, title: str = "") -> str:
    """변환 결과를 마크다운으로 정리"""
    segments = result.get("segments", [])
    lines = []

    if title:
        lines.append(f"# {title}\n")

    lines.append("## 전체 텍스트\n")
    lines.append(result.get("text", "").strip())
    lines.append("\n\n## 타임스탬프별 텍스트\n")

    for seg in segments:
        start = seg["start"]
        text = seg["text"].strip()
        if not text:
            continue
        mm, ss = divmod(int(start), 60)
        hh, mm = divmod(mm, 60)
        if hh > 0:
            ts = f"{hh:02d}:{mm:02d}:{ss:02d}"
        else:
            ts = f"{mm:02d}:{ss:02d}"
        lines.append(f"[{ts}] {text}")

    return "\n".join(lines)


def format_transcript_srt(result: dict) -> str:
    """변환 결과를 SRT 자막 포맷으로"""
    segments = result.get("segments", [])
    srt_lines = []

    for i, seg in enumerate(segments, 1):
        start = seg["start"]
        end = seg["end"]
        text = seg["text"].strip()
        if not text:
            continue

        def fmt_time(t):
            hh = int(t // 3600)
            mm = int((t % 3600) // 60)
            ss = int(t % 60)
            ms = int((t % 1) * 1000)
            return f"{hh:02d}:{mm:02d}:{ss:02d},{ms:03d}"

        srt_lines.append(str(i))
        srt_lines.append(f"{fmt_time(start)} --> {fmt_time(end)}")
        srt_lines.append(text)
        srt_lines.append("")

    return "\n".join(srt_lines)


def download_video(url: str, output_dir: str = "/tmp/stt-work") -> str:
    """YouTube URL에서 비디오를 다운로드 (프레임 추출용)"""
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "video.mp4")

    if os.path.exists(output_path):
        os.remove(output_path)

    result = subprocess.run(
        ["yt-dlp", "-f", "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]",
         "--merge-output-format", "mp4",
         "-o", output_path, url],
        capture_output=True, text=True, timeout=600
    )
    if result.returncode != 0:
        raise RuntimeError(f"비디오 다운로드 실패: {result.stderr}")

    return output_path


def extract_frames_at_timestamps(
    video_path: str,
    timestamps: list,
    output_dir: str = "/tmp/stt-work/frames"
) -> list:
    """특정 타임스탬프에서 프레임 추출"""
    os.makedirs(output_dir, exist_ok=True)

    # 기존 프레임 삭제
    for f in glob.glob(os.path.join(output_dir, "frame_*.jpg")):
        os.remove(f)

    extracted = []
    for i, ts in enumerate(timestamps):
        out_path = os.path.join(output_dir, f"frame_{i:04d}.jpg")
        result = subprocess.run(
            ["ffmpeg", "-y", "-ss", str(ts), "-i", video_path,
             "-vframes", "1", "-q:v", "2", out_path],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0 and os.path.exists(out_path):
            extracted.append({"timestamp": ts, "path": out_path, "index": i})

    return extracted


def detect_scene_changes(video_path: str, threshold: float = 0.3) -> list:
    """ffmpeg의 scene change detection으로 장면 전환점 찾기"""
    result = subprocess.run(
        ["ffmpeg", "-i", video_path,
         "-vf", f"select='gt(scene,{threshold})',showinfo",
         "-vsync", "vfr", "-f", "null", "-"],
        capture_output=True, text=True, timeout=300
    )

    timestamps = []
    for line in result.stderr.split("\n"):
        if "pts_time:" in line:
            try:
                pts_part = line.split("pts_time:")[1].split()[0]
                ts = float(pts_part)
                timestamps.append(ts)
            except (IndexError, ValueError):
                continue

    return timestamps


def build_clips(
    segments: list,
    scene_timestamps: list,
    interval: int = 30,
    max_clips: int = 50
) -> list:
    """STT 세그먼트 + 장면 전환점을 결합해서 클립 타임스탬프 선정

    전략:
    1. 장면 전환점(scene change)이 있으면 해당 시점 사용
    2. 장면 전환이 적으면 interval초 간격으로 균등 배분
    3. 각 클립에 해당 구간의 STT 텍스트를 매핑
    """
    if not segments:
        return []

    total_duration = segments[-1]["end"] if segments else 0

    # 장면 전환점 + 고정 간격 혼합
    clip_times = set()

    # 장면 전환점 추가
    for ts in scene_timestamps:
        clip_times.add(round(ts, 1))

    # 고정 간격도 추가 (장면 전환이 없는 구간 커버)
    t = 0
    while t < total_duration:
        clip_times.add(round(t, 1))
        t += interval

    # 너무 가까운 타임스탬프 병합 (5초 이내)
    sorted_times = sorted(clip_times)
    merged = []
    for ts in sorted_times:
        if not merged or ts - merged[-1] >= 5:
            merged.append(ts)

    # max_clips 제한
    if len(merged) > max_clips:
        step = len(merged) / max_clips
        merged = [merged[int(i * step)] for i in range(max_clips)]

    # 각 클립에 STT 텍스트 매핑
    clips = []
    for i, ts in enumerate(merged):
        # 이 타임스탬프 ±5초 범위의 텍스트 수집
        clip_text = []
        for seg in segments:
            if abs(seg["start"] - ts) < 10 or (seg["start"] <= ts <= seg["end"]):
                text = seg["text"].strip()
                if text and text not in clip_text:
                    clip_text.append(text)

        mm, ss = divmod(int(ts), 60)
        hh, mm = divmod(mm, 60)
        time_str = f"{hh:02d}:{mm:02d}:{ss:02d}" if hh > 0 else f"{mm:02d}:{ss:02d}"

        clips.append({
            "index": i,
            "timestamp": ts,
            "time_str": time_str,
            "text": " ".join(clip_text[:3]),  # 최대 3개 세그먼트
        })

    return clips


def extract_clips(
    url: str,
    stt_result: dict,
    output_dir: str = "/tmp/stt-work",
    interval: int = 30,
    max_clips: int = 40
) -> dict:
    """영상에서 클립(프레임+텍스트) 추출 전체 파이프라인"""
    frames_dir = os.path.join(output_dir, "frames")

    # 1. 비디오 다운로드
    video_path = download_video(url, output_dir)

    # 2. 장면 전환 감지
    scene_times = detect_scene_changes(video_path, threshold=0.3)

    # 3. 클립 타임스탬프 선정
    segments = stt_result.get("segments", [])
    clips = build_clips(segments, scene_times, interval=interval, max_clips=max_clips)

    # 4. 프레임 추출
    timestamps = [c["timestamp"] for c in clips]
    frames = extract_frames_at_timestamps(video_path, timestamps, frames_dir)

    # 5. 클립에 프레임 경로 매핑
    frame_map = {f["index"]: f["path"] for f in frames}
    for clip in clips:
        clip["frame_path"] = frame_map.get(clip["index"], "")

    return {
        "clips": clips,
        "frames_dir": frames_dir,
        "scene_changes": len(scene_times),
        "total_clips": len(clips),
    }


def process_url(
    url: str,
    language: str = "ko",
    model: str = "mlx-community/whisper-large-v3-turbo",
    output_dir: Optional[str] = None
) -> dict:
    """URL -> 다운로드 -> STT -> 문서 생성 전체 파이프라인"""
    import time

    if output_dir is None:
        output_dir = "/tmp/stt-work"

    start_time = time.time()

    # 1. 제목 가져오기
    title = get_video_title(url)

    # 2. 다운로드
    audio_path = download_audio(url, output_dir)

    # 3. STT 변환
    result = transcribe_audio(audio_path, language, model)

    elapsed = time.time() - start_time

    # 4. 포맷 생성
    md_text = format_transcript_md(result, title)
    srt_text = format_transcript_srt(result)

    # 5. 파일 저장
    os.makedirs(output_dir, exist_ok=True)
    md_path = os.path.join(output_dir, "transcript.md")
    srt_path = os.path.join(output_dir, "transcript.srt")
    json_path = os.path.join(output_dir, "transcript.json")

    with open(md_path, "w") as f:
        f.write(md_text)
    with open(srt_path, "w") as f:
        f.write(srt_text)
    with open(json_path, "w") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    return {
        "title": title,
        "text": result.get("text", ""),
        "markdown": md_text,
        "srt": srt_text,
        "segments": len(result.get("segments", [])),
        "elapsed": elapsed,
        "files": {"md": md_path, "srt": srt_path, "json": json_path}
    }
