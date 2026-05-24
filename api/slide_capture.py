"""
Slide capture: scene-detection-first approach for lecture/presentation videos.

Pipeline (per MaViLS 2024, SliTraNet 2022, community benchmarks):
  1. ffmpeg scene detection  → ~100-300 candidate timestamps (fast, ~100x realtime)
  2. Extract one frame per candidate  → fast ffmpeg seek
  3. aHash pre-filter (threshold=4)  → remove true burst duplicates only
  4. OCR on deduped candidates  → Swift Vision binary (0.49s/frame, Neural Engine)
                                   or EasyOCR fallback (3s/frame, CPU)
  5. Text similarity filter (threshold=0.85)  → save only when content changed

Benchmark (Apple Silicon, Korean+English lecture slides):
- Swift Vision (api/ocr_vision binary): 0.49s/frame, 6.2x faster, better accuracy
- EasyOCR (CPU): 3.06s/frame, fallback when binary not present
- Total for 21 videos (~150 frames each): ~25 min with Vision vs ~2.5hr with EasyOCR

Key research findings (MaViLS 2024, SliTraNet 2022):
- ffmpeg threshold 0.28-0.35 is optimal for lecture slides
- aHash threshold=4 (6% pixel diff) avoids eating progressive reveals
- OCR text similarity 0.85 captures incremental slide builds
"""
import base64
import glob
import os
import shutil
import subprocess
import tempfile
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional


_ocr_reader = None
# Compiled Swift Vision binary: api/ocr_vision (built from api/ocr_vision.swift)
_VISION_BIN = Path(__file__).parent / "ocr_vision"


def _check_vision_bin() -> bool:
    return _VISION_BIN.exists() and os.access(_VISION_BIN, os.X_OK)


def _ocr_frame_vision_bin(image_path: str) -> str:
    """Subprocess call to compiled Swift Vision binary — Neural Engine, 0.3-0.6s/frame."""
    try:
        r = subprocess.run(
            [str(_VISION_BIN), os.path.abspath(image_path)],
            capture_output=True, text=True, timeout=15,
        )
        return r.stdout.strip()
    except Exception:
        return ""


def _get_easyocr_reader(languages: Optional[list] = None):
    global _ocr_reader
    if _ocr_reader is None:
        import easyocr
        _ocr_reader = easyocr.Reader(languages or ["ko", "en"], gpu=False)
    return _ocr_reader


def _ahash(image_path: str, size: int = 8) -> str:
    from PIL import Image
    img = Image.open(image_path).convert("L").resize((size, size), Image.LANCZOS)
    pixels = list(img.getdata())
    avg = sum(pixels) / len(pixels)
    return "".join("1" if p > avg else "0" for p in pixels)


def _hamming(h1: str, h2: str) -> int:
    return sum(c1 != c2 for c1, c2 in zip(h1, h2))


def _ocr_frame(image_path: str, reader=None, min_confidence: float = 0.4) -> str:
    """OCR a frame. Priority: Swift Vision binary → EasyOCR fallback."""
    if _check_vision_bin():
        result = _ocr_frame_vision_bin(image_path)
        if result:
            return result

    # EasyOCR fallback (slower, lower accuracy, no binary present)
    if reader is None:
        return ""
    try:
        results = reader.readtext(image_path)
        return " ".join(
            text for _, text, conf in results
            if conf >= min_confidence and text.strip()
        )
    except Exception:
        return ""


def _text_similarity(a: str, b: str) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def detect_scene_timestamps(video_path: str, threshold: float = 0.3) -> list[float]:
    """
    ffmpeg scene change detection. Runs at ~100x real-time.
    Threshold 0.28-0.35 is optimal for lecture slides (community consensus).
    Returns timestamps in seconds where a scene cut was detected.
    """
    result = subprocess.run(
        ["ffmpeg", "-i", video_path,
         "-vf", f"select='gt(scene,{threshold})',showinfo",
         "-vsync", "vfr", "-f", "null", "-"],
        capture_output=True, text=True, timeout=300,
    )
    timestamps = []
    for line in result.stderr.split("\n"):
        if "pts_time:" in line:
            try:
                pts = float(line.split("pts_time:")[1].split()[0])
                timestamps.append(pts)
            except (IndexError, ValueError):
                continue

    if not timestamps or timestamps[0] > 5:
        timestamps.insert(0, 1.0)

    return sorted(timestamps)


def extract_slides_from_video(
    video_path: str,
    output_dir: str,
    scene_threshold: float = 0.3,
    ahash_threshold: int = 4,
    ocr_similarity_threshold: float = 0.85,
    max_slides: int = 200,
    languages: Optional[list] = None,
) -> list:
    """
    Extract unique slide frames from a lecture/presentation video.

    Thresholds based on MaViLS (2024) and community benchmarks:
    - scene_threshold=0.3: optimal for abrupt slide cuts (range: 0.28-0.35)
    - ahash_threshold=4: only remove near-identical burst frames (was 8, but 8 misses
      progressive text reveals where visual hash is similar but content differs)
    - ocr_similarity_threshold=0.85: skip frame if OCR text is ≥85% similar to last slide
      (MaViLS paper: OCR features are the strongest predictor of slide boundaries)
    - max_slides=200: raised from 80 for long lectures (1-3hr videos)

    Returns list of dicts:
        slide_index, timestamp, time_str, frame_path, filename, ocr_text
    """
    os.makedirs(output_dir, exist_ok=True)
    for f in glob.glob(os.path.join(output_dir, "slide_*.jpg")):
        os.remove(f)

    timestamps = detect_scene_timestamps(video_path, scene_threshold)
    if not timestamps:
        return []

    # Only load EasyOCR (slow, 3s/frame) if the Swift Vision binary isn't compiled
    reader = None if _check_vision_bin() else _get_easyocr_reader(languages)

    with tempfile.TemporaryDirectory(prefix="slides-raw-") as tmp_dir:
        raw_frames = []
        for i, ts in enumerate(timestamps):
            out_path = os.path.join(tmp_dir, f"raw_{i:04d}.jpg")
            subprocess.run(
                ["ffmpeg", "-y", "-ss", str(ts), "-i", video_path,
                 "-vframes", "1", "-q:v", "2", out_path],
                capture_output=True, timeout=15,
            )
            if os.path.exists(out_path):
                raw_frames.append({"path": out_path, "timestamp": ts})

        if not raw_frames:
            return []

        # aHash pre-filter: only removes visually near-identical burst frames
        # threshold=4 (6% pixel diff) avoids false-positive dedup of progressive reveals
        deduped = []
        seen_hashes = []
        for frame in raw_frames:
            try:
                h = _ahash(frame["path"])
            except Exception:
                continue
            if any(_hamming(h, sh) <= ahash_threshold for sh in seen_hashes):
                continue
            seen_hashes.append(h)
            deduped.append(frame)

        slides = []
        last_ocr = ""

        for frame in deduped:
            curr_ocr = _ocr_frame(frame["path"], reader)

            if slides and _text_similarity(last_ocr, curr_ocr) >= ocr_similarity_threshold:
                continue
            last_ocr = curr_ocr

            idx = len(slides)
            filename = f"slide_{idx:04d}.jpg"
            dest = os.path.join(output_dir, filename)
            shutil.copy2(frame["path"], dest)

            ts = frame["timestamp"]
            mm, ss = divmod(int(ts), 60)
            hh, mm = divmod(mm, 60)
            time_str = f"{hh:02d}:{mm:02d}:{ss:02d}" if hh > 0 else f"{mm:02d}:{ss:02d}"

            slides.append({
                "slide_index": idx,
                "timestamp": ts,
                "time_str": time_str,
                "frame_path": dest,
                "filename": filename,
                "ocr_text": curr_ocr,
            })

            if len(slides) >= max_slides:
                break

    return slides


def image_to_base64(image_path: str) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode()
