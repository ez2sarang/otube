"""
특정 플레이리스트 URL의 영상 전체 배치 처리

사용:
  python scripts/batch_playlist.py <playlist_url> [--workers 5] [--channel "채널명"] [--resume]
"""
import argparse
import json
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Optional

sys.path.insert(0, "/Users/ez2sarang/Documents/dev/ai/offline-thinking/api")
from db import execute, query
from vtt_pipeline import download_vtt, parse_vtt, parse_vtt_with_segments

lock = threading.Lock()
stats = {"ok": 0, "no_vtt": 0, "fail": 0, "skip": 0}


def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def fetch_playlist_videos(url: str) -> list:
    log(f"영상 목록 수집 중: {url}")
    result = subprocess.run(
        ["yt-dlp", "--flat-playlist",
         "--cookies-from-browser", "chrome:/tmp/chrome-cdp-gdrive",
         "--print", "%(id)s|%(title)s|%(duration)s|%(upload_date)s|%(channel)s",
         url],
        capture_output=True, text=True, timeout=180
    )
    videos = []
    channel_name = ""
    for line in result.stdout.strip().splitlines():
        parts = line.split("|")
        if len(parts) < 2:
            continue
        vid_id = parts[0]
        title = parts[1]
        try:
            duration = int(float(parts[2])) if len(parts) > 2 and parts[2] not in ("", "NA") else 0
        except Exception:
            duration = 0
        raw_date = parts[3] if len(parts) > 3 and parts[3] not in ("", "NA") else ""
        upload_date = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:8]}" if len(raw_date) == 8 else None
        if not channel_name and len(parts) > 4:
            channel_name = parts[4]
        videos.append({"id": vid_id, "title": title, "duration": duration,
                        "upload_date": upload_date, "channel": channel_name})
    log(f"수집 완료: {len(videos)}개 (채널: {channel_name})")
    return videos


def get_existing_ids() -> set:
    rows = query("SELECT id FROM stt_analysis.videos")
    return {r["id"] for r in rows}


def process_video(video: dict, channel_override: Optional[str]) -> str:
    vid_id = video["id"]
    title = video["title"]
    url = f"https://www.youtube.com/watch?v={vid_id}"
    channel = channel_override or video.get("channel") or "unknown"

    try:
        vtt_content = download_vtt(url, language="ko")
        if not vtt_content:
            vtt_content = download_vtt(url, language="en")

        if not vtt_content:
            _save_meta_only(vid_id, title, url, video["duration"], video["upload_date"], channel)
            with lock:
                stats["no_vtt"] += 1
            log(f"  ⚠ VTT없음: {title[:45]}")
            return "no_vtt"

        segments = parse_vtt_with_segments(vtt_content)
        raw_text = parse_vtt(vtt_content)

        if not raw_text.strip():
            _save_meta_only(vid_id, title, url, video["duration"], video["upload_date"], channel)
            with lock:
                stats["no_vtt"] += 1
            return "no_vtt"

        segments_json = json.dumps(segments, ensure_ascii=False) if segments else None

        execute("""
            INSERT INTO stt_analysis.videos
              (id, title, source, channel, url, duration_sec, text_length,
               segment_count, language, thumbnail, preview, upload_date)
            VALUES (%s, %s, 'youtube', %s, %s, %s, %s, %s, 'ko', %s, %s, %s)
            ON CONFLICT (id) DO NOTHING
        """, (
            vid_id, title, channel, url, video["duration"],
            len(raw_text), len(segments),
            f"https://img.youtube.com/vi/{vid_id}/mqdefault.jpg",
            raw_text[:200], video["upload_date"],
        ))

        execute("""
            INSERT INTO stt_analysis.transcripts
              (video_id, full_text, corrected_text, stt_source, correction_model, segments)
            VALUES (%s, %s, %s, 'vtt', NULL, %s)
            ON CONFLICT (video_id) DO UPDATE
              SET full_text = EXCLUDED.full_text,
                  corrected_text = EXCLUDED.corrected_text,
                  segments = EXCLUDED.segments
        """, (vid_id, raw_text, raw_text, segments_json))

        with lock:
            stats["ok"] += 1
            log(f"  ✓ [{stats['ok']}] {title[:45]} ({len(segments)}세그)")
        return "ok"

    except Exception as e:
        with lock:
            stats["fail"] += 1
        log(f"  ✗ {vid_id}: {str(e)[:60]}")
        return "fail"


def _save_meta_only(vid_id, title, url, duration, upload_date, channel):
    try:
        execute("""
            INSERT INTO stt_analysis.videos
              (id, title, source, channel, url, duration_sec, text_length,
               segment_count, language, thumbnail, preview, upload_date)
            VALUES (%s, %s, 'youtube', %s, %s, %s, 0, 0, 'ko', %s, '', %s)
            ON CONFLICT (id) DO NOTHING
        """, (
            vid_id, title, channel, url, duration,
            f"https://img.youtube.com/vi/{vid_id}/mqdefault.jpg",
            upload_date,
        ))
    except Exception:
        pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("url", help="YouTube 플레이리스트 URL")
    parser.add_argument("--workers", type=int, default=5)
    parser.add_argument("--channel", type=str, default="", help="채널명 오버라이드")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    videos = fetch_playlist_videos(args.url)
    if not videos:
        log("영상 없음. 종료.")
        return

    existing = get_existing_ids()
    todo = [v for v in videos if v["id"] not in existing]

    if args.limit > 0:
        todo = todo[:args.limit]

    log(f"전체: {len(videos)} | 기존 DB: {len(existing) - (len(videos) - len(todo))} | 처리: {len(todo)}개 | workers: {args.workers}")
    log("=" * 60)

    start = time.time()
    channel_override = args.channel or None

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(process_video, v, channel_override): v for v in todo}
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                log(f"[executor] 예외: {e}")

    elapsed = time.time() - start
    log("=" * 60)
    log(f"완료! {elapsed:.0f}초 ({elapsed/60:.1f}분)")
    log(f"  ✓ {stats['ok']} | ⚠ {stats['no_vtt']} | ✗ {stats['fail']}")


if __name__ == "__main__":
    main()
