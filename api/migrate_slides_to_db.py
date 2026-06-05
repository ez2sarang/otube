"""
기존 data/slides/ 파일시스템 데이터를 stt_analysis.slides DB로 이관.
실행: python api/migrate_slides_to_db.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SLIDES_DIR = os.path.join(PROJECT_ROOT, "data", "slides")


def migrate():
    from db import execute, query

    if not os.path.exists(SLIDES_DIR):
        print("data/slides/ 디렉토리가 없습니다. 마이그레이션 불필요.")
        return

    video_dirs = [d for d in os.listdir(SLIDES_DIR) if os.path.isdir(os.path.join(SLIDES_DIR, d))]
    print(f"총 {len(video_dirs)}개 영상 발견\n")

    done, skipped, failed = 0, 0, 0
    for vid_id in sorted(video_dirs):
        vid_dir = os.path.join(SLIDES_DIR, vid_id)
        meta_path = os.path.join(vid_dir, "meta.json")

        if not os.path.exists(meta_path):
            print(f"  [{vid_id}] meta.json 없음 → 스킵")
            skipped += 1
            continue

        # DB에 이미 있으면 스킵
        existing = query(
            "SELECT 1 FROM stt_analysis.slides WHERE video_id = %s LIMIT 1",
            (vid_id,),
        )
        if existing:
            print(f"  [{vid_id}] DB에 이미 존재 → 스킵")
            skipped += 1
            continue

        with open(meta_path, encoding="utf-8") as f:
            meta = json.load(f)

        slides = meta.get("slides", [])
        saved = 0
        for s in slides:
            img_path = os.path.join(vid_dir, s["filename"])
            if not os.path.exists(img_path):
                continue
            with open(img_path, "rb") as f:
                img_bytes = f.read()
            try:
                execute(
                    """
                    INSERT INTO stt_analysis.slides
                        (video_id, slide_index, filename, image_data, frame_time, time_str, ocr_text, llm_summary)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (video_id, slide_index) DO NOTHING
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
            except Exception as e:
                print(f"    슬라이드 {s['filename']} 저장 실패: {e}")

        # videos 테이블 slides_count 갱신
        execute(
            "UPDATE stt_analysis.videos SET slides_count = %s, slides_extracted_at = NOW() WHERE id = %s",
            (saved, vid_id),
        )

        print(f"  [{vid_id}] {saved}/{len(slides)}개 슬라이드 DB 저장 완료")
        done += 1

    print(f"\n=== 마이그레이션 완료 ===")
    print(f"성공: {done}, 스킵: {skipped}, 실패: {failed}")
    print("\n이제 data/slides/ 디렉토리를 안전하게 삭제할 수 있습니다.")


if __name__ == "__main__":
    migrate()
