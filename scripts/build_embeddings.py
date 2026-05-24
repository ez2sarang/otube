"""기존 트랜스크립트에 임베딩 생성 (배치)"""
import sys
import os
import argparse
from datetime import datetime

# api 모듈 임포트
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../api"))

from db import query, execute
import embed
from tqdm import tqdm


def build_embeddings(resume: bool = False, workers: int = 4, batch_size: int = 100):
    """
    기존 트랜스크립트에 임베딩 생성.

    Args:
        resume: True면 이미 embedded_at이 있는 것 스킵
        workers: 병렬 처리 워커 수 (현재 미사용, 순차 처리)
        batch_size: 한 번에 DB에 저장할 개수
    """
    print("[build_embeddings] Starting embedding generation...")

    # 1. 임베딩할 트랜스크립트 조회
    if resume:
        print("[build_embeddings] Resuming: skipping already embedded...")
        rows = query(
            """
            SELECT video_id, full_text
            FROM stt_analysis.transcripts
            WHERE full_text IS NOT NULL
              AND full_text != ''
              AND embedded_at IS NULL
            ORDER BY video_id
            """
        )
    else:
        print("[build_embeddings] Full rebuild: processing all...")
        rows = query(
            """
            SELECT video_id, full_text
            FROM stt_analysis.transcripts
            WHERE full_text IS NOT NULL
              AND full_text != ''
            ORDER BY video_id
            """
        )

    if not rows:
        print("[build_embeddings] No transcripts to process.")
        return

    print(f"[build_embeddings] Found {len(rows)} transcripts to embed.")

    # 2. 배치 처리
    batch = []
    batch_video_ids = []

    for row in tqdm(rows, desc="Generating embeddings", unit="transcript"):
        video_id = row["video_id"]
        text = row["full_text"]

        if not text or not text.strip():
            continue

        batch.append(text)
        batch_video_ids.append(video_id)

        # 배치 크기 도달하면 저장
        if len(batch) >= batch_size:
            _save_batch(batch, batch_video_ids)
            batch = []
            batch_video_ids = []

    # 남은 데이터 저장
    if batch:
        _save_batch(batch, batch_video_ids)

    print(
        f"[build_embeddings] ✓ Embedding generation complete! "
        f"({len(rows)} transcripts processed)"
    )


def _save_batch(texts, video_ids):
    """배치 임베딩을 DB에 저장"""
    # passage: prefix로 임베딩
    embeddings = embed.embed_batch(texts, is_query=False)

    now = datetime.utcnow().isoformat()

    # 각 트랜스크립트마다 UPDATE 실행
    for video_id, embedding in zip(video_ids, embeddings):
        embedding_str = str(embedding)  # pgvector는 string 형식
        execute(
            """
            UPDATE stt_analysis.transcripts
            SET embedding = %s::vector, embedded_at = %s
            WHERE video_id = %s
            """,
            (embedding_str, now, video_id),
        )


def main():
    parser = argparse.ArgumentParser(description="Build embeddings for transcripts")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip already embedded transcripts",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Number of parallel workers (currently unused)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Batch size for DB saves",
    )

    args = parser.parse_args()

    try:
        build_embeddings(
            resume=args.resume,
            workers=args.workers,
            batch_size=args.batch_size,
        )
    except KeyboardInterrupt:
        print("\n[build_embeddings] Interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"[build_embeddings] Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
