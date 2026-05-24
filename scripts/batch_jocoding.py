"""
조코딩 채널 전체 영상 배치 처리 스크립트

사용:
  cd /Users/ez2sarang/Documents/dev/ai/offline-thinking
  python scripts/batch_jocoding.py [--workers 5] [--limit N] [--resume]

특징:
  - ThreadPoolExecutor로 N개 병렬 처리
  - 이미 DB에 있는 영상은 자동 스킵
  - VTT 없으면 메타데이터만 저장 (Whisper 폴백은 시간 초과 우려로 스킵)
  - 멤버십 영상은 접근 실패 시 기록 후 스킵
  - /tmp/jocoding_progress.json 로 진행 상태 추적 (resume 가능)
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

CHANNEL_URL = "https://www.youtube.com/@jocoding/videos"
PROGRESS_FILE = "/tmp/jocoding_progress.json"
VIDEO_LIST_FILE = "/tmp/jocoding_all.json"

lock = threading.Lock()
stats = {"ok": 0, "skip": 0, "fail": 0, "no_vtt": 0, "membership": 0}


def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def fetch_channel_videos():
    log("채널 영상 목록 수집 중...")
    result = subprocess.run(
        ["yt-dlp", "--flat-playlist", "--cookies-from-browser", "chrome",
         "--print", "%(id)s|%(title)s|%(duration)s|%(upload_date)s",
         CHANNEL_URL],
        capture_output=True, text=True, timeout=120
    )
    videos = []
    for line in result.stdout.strip().splitlines():
        parts = line.split("|")
        if len(parts) < 4:
            continue
        vid_id = parts[0]
        upload_date_raw = parts[-1]
        duration_raw = parts[-2]
        title = "|".join(parts[1:-2])
        try:
            duration = int(float(duration_raw)) if duration_raw not in ("", "NA") else 0
        except Exception:
            duration = 0
        upload_date = None
        if len(upload_date_raw) == 8 and upload_date_raw.isdigit():
            d = upload_date_raw
            upload_date = f"{d[:4]}-{d[4:6]}-{d[6:8]}"
        videos.append({"id": vid_id, "title": title, "duration": duration, "upload_date": upload_date})

    with open(VIDEO_LIST_FILE, "w") as f:
        json.dump(videos, f, ensure_ascii=False, indent=2)
    log(f"수집 완료: {len(videos)}개")
    return videos


def get_existing_ids():
    rows = query("SELECT id FROM stt_analysis.videos")
    return {r["id"] for r in rows}


def load_progress():
    try:
        with open(PROGRESS_FILE) as f:
            return set(json.load(f).get("done", []))
    except Exception:
        return set()


def save_progress(done_ids: set):
    with open(PROGRESS_FILE, "w") as f:
        json.dump({"done": list(done_ids), "updated": datetime.now().isoformat()}, f)


def is_membership_video(title: str) -> bool:
    """제목에 멤버십 표시가 있는지 확인"""
    return "(Membership)" in title or "(멤버십)" in title


def process_video(video: dict, progress_done: set) -> str:
    vid_id = video["id"]
    title = video["title"]
    url = f"https://www.youtube.com/watch?v={vid_id}"

    # 멤버십 영상 표시
    is_member = is_membership_video(title)

    try:
        # VTT 다운로드 시도
        vtt_content = None
        try:
            vtt_content = download_vtt(url, language="ko")
        except Exception as e:
            err_str = str(e)
            if "members-only" in err_str or "Join this channel" in err_str:
                with lock:
                    stats["membership"] += 1
                log(f"  🔒 멤버십전용: {title[:45]}")
                # 메타데이터만 저장
                _save_meta_only(vid_id, title, url, video["duration"], video["upload_date"])
                return "membership"
            raise

        if not vtt_content:
            with lock:
                stats["no_vtt"] += 1
            log(f"  ⚠ VTT없음: {title[:45]}")
            _save_meta_only(vid_id, title, url, video["duration"], video["upload_date"])
            return "no_vtt"

        # VTT 파싱
        segments = parse_vtt_with_segments(vtt_content)
        raw_text = parse_vtt(vtt_content)

        if not raw_text.strip():
            _save_meta_only(vid_id, title, url, video["duration"], video["upload_date"])
            return "no_vtt"

        segments_json = json.dumps(segments, ensure_ascii=False) if segments else None

        # videos 테이블 저장
        execute("""
            INSERT INTO stt_analysis.videos
              (id, title, source, channel, url, duration_sec, text_length,
               segment_count, language, thumbnail, preview, upload_date)
            VALUES (%s, %s, 'youtube', '조코딩', %s, %s, %s, %s, 'ko', %s, %s, %s)
            ON CONFLICT (id) DO NOTHING
        """, (
            vid_id, title, url, video["duration"],
            len(raw_text), len(segments),
            f"https://img.youtube.com/vi/{vid_id}/mqdefault.jpg",
            raw_text[:200],
            video["upload_date"],
        ))

        # transcripts 테이블 저장
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
            progress_done.add(vid_id)
            if stats["ok"] % 10 == 0:
                save_progress(progress_done)

        log(f"  ✓ [{stats['ok']}] {title[:45]} ({len(segments)}세그)")
        return "ok"

    except Exception as e:
        err = str(e)
        if "members-only" in err or "Join this channel" in err:
            with lock:
                stats["membership"] += 1
            _save_meta_only(vid_id, title, url, video["duration"], video["upload_date"])
            log(f"  🔒 멤버십전용: {title[:45]}")
            return "membership"

        with lock:
            stats["fail"] += 1
        log(f"  ✗ 실패 {vid_id}: {err[:80]}")
        return "fail"


def _save_meta_only(vid_id, title, url, duration, upload_date):
    """VTT 없거나 멤버십 영상: 메타데이터만 저장"""
    try:
        execute("""
            INSERT INTO stt_analysis.videos
              (id, title, source, channel, url, duration_sec, text_length,
               segment_count, language, thumbnail, preview, upload_date)
            VALUES (%s, %s, 'youtube', '조코딩', %s, %s, 0, 0, 'ko', %s, '', %s)
            ON CONFLICT (id) DO NOTHING
        """, (
            vid_id, title, url, duration,
            f"https://img.youtube.com/vi/{vid_id}/mqdefault.jpg",
            upload_date,
        ))
    except Exception:
        pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=5, help="병렬 처리 worker 수")
    parser.add_argument("--limit", type=int, default=0, help="처리할 최대 영상 수 (0=전체)")
    parser.add_argument("--resume", action="store_true", help="이전 진행 상태에서 재시작")
    parser.add_argument("--fetch", action="store_true", help="채널 영상 목록 재수집")
    args = parser.parse_args()

    # 영상 목록 로드
    if args.fetch or not __import__("os").path.exists(VIDEO_LIST_FILE):
        all_videos = fetch_channel_videos()
    else:
        with open(VIDEO_LIST_FILE) as f:
            all_videos = json.load(f)
        log(f"기존 목록 사용: {len(all_videos)}개")

    # DB에 이미 있는 영상 제외
    existing = get_existing_ids()
    log(f"DB 기존: {len(existing)}개")

    # resume 모드: 이전 진행 기록 로드
    progress_done = load_progress() if args.resume else set()

    # 처리 대상 필터링
    todo = [v for v in all_videos if v["id"] not in existing and v["id"] not in progress_done]

    if args.limit > 0:
        todo = todo[:args.limit]

    log(f"처리 대상: {len(todo)}개 | workers: {args.workers}")
    log("=" * 60)

    start = time.time()

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(process_video, v, progress_done): v for v in todo}
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                log(f"  [executor] 예외: {e}")

    elapsed = time.time() - start
    save_progress(progress_done)

    log("=" * 60)
    log(f"완료! 소요: {elapsed:.0f}초 ({elapsed/60:.1f}분)")
    log(f"  ✓ 성공:      {stats['ok']}")
    log(f"  ⚠ VTT없음:   {stats['no_vtt']}")
    log(f"  🔒 멤버십:   {stats['membership']}")
    log(f"  ✗ 실패:      {stats['fail']}")
    log(f"  ↷ 스킵(DB): {stats['skip']}")


if __name__ == "__main__":
    main()
