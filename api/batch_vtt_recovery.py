"""
대항해시대 영상 배치 복구 스크립트 — VTT raw 텍스트만 DB 저장 (LLM/OCR/슬라이드 스킵)
사용: python batch_vtt_recovery.py [--workers 3] [--limit N]
"""
import argparse
import json
import re
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

sys.path.insert(0, "/Users/ez2sarang/Documents/dev/ai/offline-thinking/api")
from db import execute, query
from vtt_pipeline import download_vtt, parse_vtt, parse_vtt_with_segments


CHANNEL_URL = "https://www.youtube.com/@%EA%B2%8C%EC%9E%84%ED%95%98%EB%8A%94%EB%B0%B1%ED%95%9C%EB%9F%89/videos"
KEYWORD = "대항해시대"

lock = threading.Lock()
stats = {"ok": 0, "skip": 0, "fail": 0, "no_vtt": 0}


def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def fetch_channel_videos():
    log("채널 영상 목록 수집 중...")
    result = subprocess.run(
        ["yt-dlp", "--flat-playlist", "--print", "%(id)s|%(title)s|%(duration)s|%(upload_date)s",
         "--cookies-from-browser", "chrome", CHANNEL_URL],
        capture_output=True, text=True, timeout=120
    )
    videos = []
    for line in result.stdout.strip().splitlines():
        parts = line.split("|")
        if len(parts) < 2:
            continue
        vid_id, title = parts[0], parts[1]
        duration = int(float(parts[2])) if len(parts) > 2 and parts[2] not in ("", "NA") else 0
        raw_date = parts[3] if len(parts) > 3 and parts[3] not in ("", "NA") else ""
        upload_date = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:8]}" if len(raw_date) == 8 else None
        if KEYWORD in title:
            videos.append({"id": vid_id, "title": title, "duration": duration, "upload_date": upload_date})
    return videos


def get_existing_ids():
    rows = query("SELECT id FROM stt_analysis.videos")
    return {r["id"] for r in rows}


def process_video(video):
    vid_id = video["id"]
    title = video["title"]
    url = f"https://www.youtube.com/watch?v={vid_id}"

    try:
        vtt_content = download_vtt(url, language="ko")
        if not vtt_content:
            with lock:
                stats["no_vtt"] += 1
            log(f"  ⚠ VTT없음: {title[:40]}")
            # VTT 없어도 메타데이터만 DB 저장
            execute("""
                INSERT INTO stt_analysis.videos
                  (id, title, source, channel, url, duration_sec, text_length,
                   segment_count, language, thumbnail, preview, upload_date)
                VALUES (%s,%s,'youtube','게임하는백한량',%s,%s,0,0,'ko',%s,'',%s)
                ON CONFLICT (id) DO NOTHING
            """, (
                vid_id, title, url, video["duration"],
                f"https://img.youtube.com/vi/{vid_id}/mqdefault.jpg",
                video["upload_date"],
            ))
            return "no_vtt"

        raw_text = parse_vtt(vtt_content)
        segments = parse_vtt_with_segments(vtt_content)

        execute("""
            INSERT INTO stt_analysis.videos
              (id, title, source, channel, url, duration_sec, text_length,
               segment_count, language, thumbnail, preview, upload_date)
            VALUES (%s,%s,'youtube','게임하는백한량',%s,%s,%s,%s,'ko',%s,%s,%s)
            ON CONFLICT (id) DO NOTHING
        """, (
            vid_id, title, url, video["duration"],
            len(raw_text), len(segments),
            f"https://img.youtube.com/vi/{vid_id}/mqdefault.jpg",
            raw_text[:200],
            video["upload_date"],
        ))

        execute("""
            INSERT INTO stt_analysis.transcripts
              (video_id, full_text, corrected_text, stt_source, correction_model, segments)
            VALUES (%s,%s,%s,'vtt_raw',NULL,%s)
            ON CONFLICT (video_id) DO NOTHING
        """, (
            vid_id, raw_text, raw_text,
            json.dumps(segments, ensure_ascii=False),
        ))

        with lock:
            stats["ok"] += 1
        return "ok"

    except Exception as e:
        with lock:
            stats["fail"] += 1
        log(f"  ✗ 실패 [{vid_id}] {str(e)[:60]}")
        return "fail"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    videos = fetch_channel_videos()
    log(f"채널 전체 대항해시대 영상: {len(videos)}개")

    existing = get_existing_ids()
    todo = [v for v in videos if v["id"] not in existing]
    log(f"기존 DB: {len(existing)}개 / 신규 처리 대상: {len(todo)}개")

    if args.limit:
        todo = todo[:args.limit]
        log(f"  → --limit {args.limit} 적용")

    if not todo:
        log("처리할 영상이 없습니다.")
        return

    total = len(todo)
    done = [0]

    def wrapped(video):
        result = process_video(video)
        with lock:
            done[0] += 1
            if done[0] % 10 == 0 or done[0] == total:
                pct = done[0] / total * 100
                log(f"  진행: {done[0]}/{total} ({pct:.1f}%) | ✓{stats['ok']} ⚠{stats['no_vtt']} ✗{stats['fail']}")
        return result

    log(f"배치 시작 (workers={args.workers}) ...")
    start = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = [ex.submit(wrapped, v) for v in todo]
        for f in as_completed(futures):
            pass

    elapsed = time.time() - start
    log(f"\n완료 — {elapsed:.0f}초")
    log(f"  성공: {stats['ok']} | VTT없음: {stats['no_vtt']} | 실패: {stats['fail']}")


if __name__ == "__main__":
    main()
