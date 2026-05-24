#!/usr/bin/env python3
"""Correct auto-generated Korean subtitles from Uncharted Waters Online livestream transcripts."""

import sys
sys.path.insert(0, '/Users/ez2sarang/Documents/dev/ai/offline-thinking/api')

from db import query, execute

# Correction rules mapping: (original, corrected)
CORRECTIONS = [
    ("대학일", "대항해시대"),
    ("대학의 시대", "대항해시대"),
    ("대대", "대항해시대"),
    ("대항의 시대", "대항해시대"),
    ("공해", "공예"),  # crafting skill
    ("난만", "남만"),  # 남만도래/남만교역
    ("냉작", "랭작"),
    ("공원도", "공헌도"),
    ("대감사재", "대감사제"),
    ("머사제", "대감사제"),
    ("유비 안내서", "뉴비 안내서"),
    ("개체 중", "개최 중"),
    ("철토", "철도"),
    ("부효들", "부효과들"),
]


def apply_corrections(text):
    """Apply all correction rules to the text."""
    if not text:
        return text

    corrected = text
    for original, replacement in CORRECTIONS:
        corrected = corrected.replace(original, replacement)
    return corrected


def main():
    # Query 50 uncorrected transcripts, OFFSET 50
    sql = """
    SELECT video_id, full_text
    FROM stt_analysis.transcripts
    WHERE corrected_text IS NULL AND full_text IS NOT NULL
    ORDER BY LENGTH(full_text) ASC
    LIMIT 50 OFFSET 50
    """

    rows = query(sql)

    if not rows:
        print("No transcripts to correct.")
        return

    print(f"Processing {len(rows)} transcripts...")
    corrected_count = 0

    for row in rows:
        video_id = row['video_id']
        full_text = row['full_text']

        # Apply corrections
        corrected_text = apply_corrections(full_text)

        # Only update if there were changes
        if corrected_text != full_text:
            update_sql = """
            UPDATE stt_analysis.transcripts
            SET corrected_text = %s
            WHERE video_id = %s
            """
            execute(update_sql, (corrected_text, video_id))
            corrected_count += 1
            print(f"  ✓ {video_id}")

    print(f"\nCompleted: {corrected_count}/{len(rows)} transcripts updated")


if __name__ == "__main__":
    main()
