import sys
sys.path.insert(0, '.')
from db import get_conn

CORRECTIONS = {
    '대학일': '대항해시대', '대학의 시대': '대항해시대', '대항의 시대': '대항해시대',
    '대대 사랑하는': '대항해시대 사랑하는',
    '공해 학술': '공예 학술', '공해 랭': '공예 랭', '공해 마터': '공예 마터',
    '난만 교역': '남만 교역', '난만도래': '남만도래', '난만이': '남만이', '난만 맥스': '남만 맥스',
    '냉작': '랭작', '공원도': '공헌도',
    '대감사재': '대감사제', '머사제': '대감사제',
    '유비 안내서': '뉴비 안내서', '유비안내서': '뉴비 안내서',
    '개체 중': '개최 중', '철토 효과': '철도 효과', '부효들': '부효과들',
}

conn = get_conn()
cur = conn.cursor()
cur.execute("SELECT video_id, full_text FROM stt_analysis.transcripts WHERE corrected_text IS NULL AND full_text IS NOT NULL ORDER BY LENGTH(full_text) ASC LIMIT 50 OFFSET 100")
rows = cur.fetchall()

count = 0
for vid, text in rows:
    corrected = text
    for old, new in CORRECTIONS.items():
        corrected = corrected.replace(old, new)
    cur.execute("UPDATE stt_analysis.transcripts SET corrected_text = %s, correction_model = 'claude-haiku' WHERE video_id = %s", (corrected, vid))
    count += 1

conn.commit()
cur.close()
conn.close()
print(f"Corrected: {count}")
