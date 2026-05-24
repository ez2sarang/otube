"""Video OCR pipeline: frame extraction + deduplication + text recognition"""
import os
import subprocess
import tempfile
import shutil
from pathlib import Path


# EasyOCR reader singleton (초기화 비용이 크므로 재사용)
_ocr_reader = None


def _get_reader(languages=None):
    global _ocr_reader
    if _ocr_reader is None:
        import easyocr
        langs = languages or ["ko", "en"]
        _ocr_reader = easyocr.Reader(langs, gpu=False)
    return _ocr_reader


def get_video_stream_url(yt_url):
    """yt-dlp로 직접 스트리밍 URL 추출 (전체 다운로드 불필요)"""
    result = subprocess.run(
        ["yt-dlp", "-g", "-f", "worst[ext=mp4]/worst", yt_url],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return None
    return result.stdout.strip().split("\n")[0]


def extract_frames(video_source, output_dir, fps=0.2):
    """
    ffmpeg으로 프레임 추출.
    video_source: 파일 경로 또는 직접 스트리밍 URL
    fps: 초당 프레임 수 (0.2 = 5초에 1장)
    """
    result = subprocess.run(
        [
            "ffmpeg", "-i", video_source,
            "-vf", f"fps={fps}",
            "-q:v", "3",  # JPEG 품질 (낮을수록 좋음, 2~5 권장)
            "-frames:v", "600",  # 최대 600장 (fps=0.2 기준 약 50분)
            os.path.join(output_dir, "frame_%04d.jpg"),
        ],
        capture_output=True, timeout=300,
    )
    return result.returncode == 0


def _phash(image_path):
    """PIL 기반 퍼셉추얼 해시 계산"""
    from PIL import Image
    import imagehash
    with Image.open(image_path) as img:
        return imagehash.phash(img)


def deduplicate_frames(frame_dir, threshold=8):
    """
    지각적 해시(pHash)로 중복 프레임 제거.
    threshold: 해시 거리 기준 (낮을수록 엄격, 8~12 권장)
    반환: 중복이 제거된 프레임 경로 목록 (정렬 순)
    """
    frames = sorted(Path(frame_dir).glob("frame_*.jpg"))
    unique = []
    last_hash = None

    for frame_path in frames:
        try:
            curr_hash = _phash(str(frame_path))
        except Exception:
            continue

        if last_hash is None or (curr_hash - last_hash) > threshold:
            unique.append(str(frame_path))
            last_hash = curr_hash

    return unique


def ocr_frame(image_path, reader, min_confidence=0.5):
    """단일 프레임에 OCR 실행. 신뢰도 threshold 이상 텍스트만 반환."""
    try:
        results = reader.readtext(image_path)
        texts = [
            text
            for _, text, conf in results
            if conf >= min_confidence and text.strip()
        ]
        return " ".join(texts)
    except Exception:
        return ""


def extract_text_from_video(yt_url, language="ko", fps=0.2, dedup_threshold=8):
    """
    유튜브 영상 OCR 전체 파이프라인.

    1. yt-dlp로 스트리밍 URL 추출
    2. ffmpeg으로 프레임 추출 (fps 간격)
    3. pHash 중복 제거
    4. EasyOCR로 텍스트 추출
    5. 텍스트 레벨 중복 제거 후 반환

    반환:
        {"frames_total": N, "frames_unique": M, "text": "..."}
        실패 시 None
    """
    langs = ["ko", "en"] if language == "ko" else [language, "en"]
    reader = _get_reader(langs)

    tmp_dir = tempfile.mkdtemp(prefix="ocr-")
    try:
        frame_dir = os.path.join(tmp_dir, "frames")
        os.makedirs(frame_dir)

        # 스트리밍 URL 추출
        stream_url = get_video_stream_url(yt_url)
        if not stream_url:
            return None

        # 프레임 추출
        ok = extract_frames(stream_url, frame_dir, fps=fps)
        if not ok:
            return None

        all_frames = list(Path(frame_dir).glob("frame_*.jpg"))
        if not all_frames:
            return None

        # 중복 제거
        unique_frames = deduplicate_frames(frame_dir, threshold=dedup_threshold)

        # OCR 실행 + 텍스트 중복 제거
        seen_texts = set()
        text_lines = []

        for frame_path in unique_frames:
            text = ocr_frame(frame_path, reader)
            if text and text not in seen_texts:
                seen_texts.add(text)
                text_lines.append(text)

        return {
            "frames_total": len(all_frames),
            "frames_unique": len(unique_frames),
            "text": "\n".join(text_lines),
        }

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
