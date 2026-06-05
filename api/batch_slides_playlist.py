"""
플레이리스트 슬라이드 배치 추출기 — DB 저장 모드

사용법:
  python batch_slides_playlist.py <playlist_url> [--analyze]

  --analyze : 각 슬라이드를 LLM으로 분석해서 DB에 summary 추가
              (시간이 오래 걸림 — 슬라이드 수 × API 호출)

저장: stt_analysis.slides (BYTEA) + stt_analysis.videos (slides_count, slides_extracted_at)
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))


def get_playlist_videos(playlist_url: str) -> list[dict]:
    """yt-dlp로 플레이리스트 영상 목록 추출."""
    result = subprocess.run(
        ["yt-dlp", "--flat-playlist",
         "--print", "%(id)s\t%(title)s\t%(webpage_url)s",
         playlist_url],
        capture_output=True, text=True, timeout=60,
    )
    if result.returncode != 0:
        print(f"[ERROR] 플레이리스트 추출 실패: {result.stderr[:200]}")
        return []

    videos = []
    for line in result.stdout.strip().split("\n"):
        parts = line.split("\t")
        if len(parts) >= 3:
            vid_id, title, url = parts[0], parts[1], parts[2]
        elif len(parts) == 2:
            vid_id, title = parts
            url = f"https://youtu.be/{vid_id}"
        else:
            continue
        videos.append({"id": vid_id, "title": title, "url": url})

    return videos


def download_video(url: str, tmp_dir: str) -> str:
    """720p 이하 mp4로 다운로드. 경로 반환."""
    os.makedirs(tmp_dir, exist_ok=True)
    out_path = os.path.join(tmp_dir, "video.mp4")
    if os.path.exists(out_path):
        os.remove(out_path)

    result = subprocess.run(
        ["yt-dlp",
         "--cookies-from-browser", "chrome",
         "-f", "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]",
         "--merge-output-format", "mp4",
         "-o", out_path, url],
        capture_output=True, text=True, timeout=600,
    )
    if result.returncode != 0 or not os.path.exists(out_path):
        raise RuntimeError(f"다운로드 실패: {result.stderr[:200]}")
    return out_path


def _slides_in_db(vid_id: str) -> bool:
    """DB에 해당 영상 슬라이드가 이미 있는지 확인."""
    from db import query
    rows = query(
        "SELECT 1 FROM stt_analysis.slides WHERE video_id = %s LIMIT 1",
        (vid_id,),
    )
    return bool(rows)


def save_slides_to_db(vid_id: str, video: dict, slides: list, tmp_slides_dir: str) -> int:
    """추출된 슬라이드를 DB에 저장. 저장된 슬라이드 수 반환."""
    from db import execute

    saved = 0
    for s in slides:
        img_path = s.get("frame_path") or os.path.join(tmp_slides_dir, s["filename"])
        if not os.path.exists(img_path):
            continue
        with open(img_path, "rb") as f:
            img_bytes = f.read()

        execute(
            """
            INSERT INTO stt_analysis.slides
                (video_id, slide_index, filename, image_data, frame_time, time_str, ocr_text, llm_summary)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (video_id, slide_index) DO UPDATE SET
                image_data   = EXCLUDED.image_data,
                ocr_text     = EXCLUDED.ocr_text,
                llm_summary  = EXCLUDED.llm_summary
            """,
            (
                vid_id,
                s["slide_index"],
                s["filename"],
                img_bytes,
                s.get("timestamp"),
                s.get("time_str"),
                s.get("ocr_text", ""),
                s.get("llm_summary", ""),
            ),
        )
        saved += 1

    # videos 테이블에 슬라이드 수 갱신
    execute(
        """
        UPDATE stt_analysis.videos
        SET slides_count = %s, slides_extracted_at = NOW()
        WHERE id = %s
        """,
        (saved, vid_id),
    )
    return saved


def process_video(
    video: dict,
    analyze: bool = False,
    scene_threshold: float = 0.15,
    ocr_similarity_threshold: float = 0.85,
) -> dict:
    """단일 영상 처리. 슬라이드 추출 → DB 저장 (로컬 파일 정리)."""
    from slide_capture import extract_slides_from_video
    from llm_gateway import call_llm_with_image

    vid_id = video["id"]

    if _slides_in_db(vid_id):
        return {"status": "skipped", "video_id": vid_id}

    tmp_dir = f"/tmp/slides-batch/{vid_id}"
    tmp_slides_dir = os.path.join(tmp_dir, "slides")
    try:
        video_path = download_video(video["url"], tmp_dir)
        slides = extract_slides_from_video(
            video_path, tmp_slides_dir,
            scene_threshold=scene_threshold,
            ocr_similarity_threshold=ocr_similarity_threshold,
        )
        # 0개 추출 시 임계값을 절반으로 낮춰 1회 자동 재시도
        if not slides and scene_threshold > 0.08:
            retry_threshold = round(scene_threshold / 2, 3)
            slides = extract_slides_from_video(
                video_path, tmp_slides_dir,
                scene_threshold=retry_threshold,
                ocr_similarity_threshold=ocr_similarity_threshold,
            )

        if analyze and slides:
            task = "이 강의 슬라이드의 핵심 내용을 2~3문장으로 요약해줘."
            for slide in slides:
                summary = call_llm_with_image(
                    task=task,
                    image_path=slide.get("frame_path", os.path.join(tmp_slides_dir, slide["filename"])),
                    ocr_text=slide.get("ocr_text", ""),
                )
                slide["llm_summary"] = summary or ""
                time.sleep(0.5)

        saved = save_slides_to_db(vid_id, video, slides, tmp_slides_dir)
        return {"status": "ok", "video_id": vid_id, "slides": saved}

    except Exception as e:
        return {"status": "error", "video_id": vid_id, "error": str(e)[:120]}
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def main():
    parser = argparse.ArgumentParser(description="플레이리스트 슬라이드 배치 추출 (DB 저장)")
    parser.add_argument("playlist_url", help="YouTube 플레이리스트 URL")
    parser.add_argument("--analyze", action="store_true",
                        help="각 슬라이드를 LLM으로 분석 (느림)")
    parser.add_argument("--scene-threshold", type=float, default=0.15,
                        help="ffmpeg 씬 감지 임계값 (기본: 0.15, 범위: 0.08-0.30)")
    parser.add_argument("--ocr-similarity", type=float, default=0.85,
                        help="OCR 텍스트 유사도 임계값 (기본: 0.85)")
    args = parser.parse_args()

    print("플레이리스트 영상 목록 가져오는 중...")
    videos = get_playlist_videos(args.playlist_url)
    if not videos:
        print("영상을 찾을 수 없습니다.")
        sys.exit(1)

    print(f"총 {len(videos)}개 영상\n")

    done, skipped, failed = 0, 0, 0
    for i, video in enumerate(videos):
        title_short = video["title"][:50]
        print(f"[{i+1}/{len(videos)}] {title_short}...")

        result = process_video(
            video,
            analyze=args.analyze,
            scene_threshold=args.scene_threshold,
            ocr_similarity_threshold=args.ocr_similarity,
        )

        if result["status"] == "ok":
            done += 1
            print(f"  OK: {result['slides']}개 슬라이드 → DB 저장")
        elif result["status"] == "skipped":
            skipped += 1
            print("  SKIP (DB에 이미 존재)")
        else:
            failed += 1
            print(f"  FAIL: {result.get('error', '알 수 없는 오류')}")

    print(f"\n=== 완료 ===")
    print(f"성공: {done}, 스킵: {skipped}, 실패: {failed} / 전체: {len(videos)}")
    print("저장 위치: stt_analysis.slides (DB)")


if __name__ == "__main__":
    main()
