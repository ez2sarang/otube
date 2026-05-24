"""
조코딩 멤버십 영상 재처리 스크립트 — CDP Chrome 프로파일 쿠키 사용

사용:
  cd /Users/ez2sarang/Documents/dev/ai/offline-thinking
  python scripts/retry_membership_jocoding.py
"""

import json
import re
import subprocess
import sys
from datetime import datetime
from typing import Optional

sys.path.insert(0, "/Users/ez2sarang/Documents/dev/ai/offline-thinking/api")
from db import execute, query
from vtt_pipeline import parse_vtt, parse_vtt_with_segments

CDP_PROFILE = "/tmp/chrome-cdp-gdrive"
CHANNEL = "조코딩"


def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def download_vtt_cdp(url: str, language: str = "ko") -> Optional[str]:
    """CDP Chrome 프로파일 쿠키로 VTT 다운로드"""
    import tempfile, os, shutil
    tmp_dir = tempfile.mkdtemp(prefix="vtt-cdp-")
    try:
        result = subprocess.run(
            ["yt-dlp",
             f"--cookies-from-browser", f"chrome:{CDP_PROFILE}",
             "--write-auto-sub", "--sub-lang", language,
             "--skip-download", "--sub-format", "vtt",
             "-o", os.path.join(tmp_dir, "sub"), url],
            capture_output=True, text=True, timeout=60
        )
        vtt_path = os.path.join(tmp_dir, f"sub.{language}.vtt")
        if not os.path.exists(vtt_path):
            return None
        with open(vtt_path) as f:
            content = f.read()
        return content
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def get_membership_videos():
    """DB에서 조코딩 채널 중 transcript가 비어있는 멤버십 영상 조회"""
    rows = query("""
        SELECT v.id, v.title, v.url, v.duration_sec, v.upload_date
        FROM stt_analysis.videos v
        LEFT JOIN stt_analysis.transcripts t ON v.id = t.video_id
        WHERE v.channel = %s
          AND (t.video_id IS NULL OR t.full_text = '' OR t.full_text IS NULL)
        ORDER BY v.title
    """, (CHANNEL,))
    return list(rows)


def process_membership_video(video: dict) -> str:
    vid_id = video["id"]
    title = video["title"]
    url = video["url"] or f"https://www.youtube.com/watch?v={vid_id}"

    log(f"처리 중: {title[:55]}")

    try:
        vtt_content = download_vtt_cdp(url, language="ko")
        if not vtt_content:
            # 영어 시도
            vtt_content = download_vtt_cdp(url, language="en")

        if not vtt_content:
            log(f"  ⚠ VTT없음 (쿠키 있어도 자막 없음): {title[:45]}")
            return "no_vtt"

        segments = parse_vtt_with_segments(vtt_content)
        raw_text = parse_vtt(vtt_content)

        if not raw_text.strip():
            log(f"  ⚠ 빈 텍스트: {title[:45]}")
            return "empty"

        segments_json = json.dumps(segments, ensure_ascii=False) if segments else None

        # transcript 저장/업데이트
        execute("""
            INSERT INTO stt_analysis.transcripts
              (video_id, full_text, corrected_text, stt_source, correction_model, segments)
            VALUES (%s, %s, %s, 'vtt', NULL, %s)
            ON CONFLICT (video_id) DO UPDATE
              SET full_text = EXCLUDED.full_text,
                  corrected_text = EXCLUDED.corrected_text,
                  segments = EXCLUDED.segments
        """, (vid_id, raw_text, raw_text, segments_json))

        # videos 텍스트 길이 + 세그먼트 수 업데이트
        execute("""
            UPDATE stt_analysis.videos
            SET text_length = %s, segment_count = %s, preview = %s
            WHERE id = %s
        """, (len(raw_text), len(segments), raw_text[:200], vid_id))

        log(f"  ✓ {title[:45]} ({len(segments)}세그)")
        return "ok"

    except Exception as e:
        log(f"  ✗ 실패: {e}")
        return "fail"


def main():
    log("조코딩 멤버십 영상 재처리 시작 (CDP 프로파일 쿠키)")
    log(f"CDP 프로파일: {CDP_PROFILE}")

    # 쿠키 테스트
    test = subprocess.run(
        ["yt-dlp", f"--cookies-from-browser", f"chrome:{CDP_PROFILE}",
         "--print", "%(title)s", "--no-download",
         "https://www.youtube.com/watch?v=RXG3qn1ziIU"],
        capture_output=True, text=True, timeout=30
    )
    if test.returncode == 0:
        log("✓ CDP 쿠키 멤버십 접근 확인됨")
    else:
        log(f"✗ CDP 쿠키 문제: {test.stderr[:100]}")
        log("Chrome을 CDP 프로파일로 실행하고 YouTube 멤버십 로그인 필요")
        return

    videos = get_membership_videos()
    log(f"처리 대상: {len(videos)}개 (transcript 없는 영상)")

    stats = {"ok": 0, "no_vtt": 0, "fail": 0}
    for v in videos:
        result = process_membership_video(v)
        stats[result] = stats.get(result, 0) + 1

    log("=" * 50)
    log(f"완료! ✓ {stats['ok']} | ⚠ VTT없음 {stats.get('no_vtt',0)} | ✗ {stats.get('fail',0)}")


if __name__ == "__main__":
    main()
