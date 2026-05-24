"""모든 영상의 텍스트 프레임을 배치 추출"""
import json
import os
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
INDEX_PATH = os.path.join(PROJECT_ROOT, "data", "index.json")
CLIPS_DIR = os.path.join(PROJECT_ROOT, "data", "clips")

from transcribe import download_video, extract_unique_text_frames


def main():
    with open(INDEX_PATH) as f:
        items = json.load(f)

    total = len(items)
    done = 0
    skipped = 0
    failed = 0

    for i, item in enumerate(items):
        vid = item["id"]
        clips_dir = os.path.join(CLIPS_DIR, vid)
        meta_path = os.path.join(clips_dir, "meta.json")

        if os.path.exists(meta_path):
            skipped += 1
            print(f"[{i+1}/{total}] SKIP: {item['title'][:40]}... (already done)")
            continue

        print(f"[{i+1}/{total}] EXTRACT: {item['title'][:40]}...")

        try:
            # 비디오 다운로드
            tmp_dir = f"/tmp/stt-work/frames-batch/{vid}"
            url = item.get("url", f"https://youtu.be/{vid}")
            video_path = download_video(url, tmp_dir)

            # 프레임 추출 + 중복 제거
            frames = extract_unique_text_frames(
                video_path, clips_dir,
                scene_threshold=0.25,
                similarity_threshold=8,
                max_frames=40,
            )

            # 메타데이터 저장
            meta = {
                "video_id": vid,
                "title": item.get("title", ""),
                "url": url,
                "frames": [
                    {"index": f["index"], "timestamp": f["timestamp"],
                     "time_str": f["time_str"], "filename": f["filename"]}
                    for f in frames
                ],
                "total_unique": len(frames),
                "extracted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            with open(meta_path, "w") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)

            # 비디오 삭제
            shutil.rmtree(tmp_dir, ignore_errors=True)

            done += 1
            print(f"  OK: {len(frames)} frames extracted")

        except Exception as e:
            failed += 1
            print(f"  FAIL: {str(e)[:80]}")
            # tmp 정리
            shutil.rmtree(f"/tmp/stt-work/frames-batch/{vid}", ignore_errors=True)

    print(f"\n=== BATCH FRAMES COMPLETE ===")
    print(f"완료: {done}, 스킵: {skipped}, 실패: {failed} / 전체: {total}")


if __name__ == "__main__":
    main()
