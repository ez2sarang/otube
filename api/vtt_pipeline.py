"""VTT download and LLM correction pipeline"""
import subprocess
import re
import os


def _yt_base_cmd():
    """yt-dlp 기본 명령어 (CDP 프로파일 쿠키 우선, 없으면 기본 Chrome)"""
    cmd = ["yt-dlp"]
    cdp_profile = "/tmp/chrome-cdp-gdrive"
    if os.path.isdir(cdp_profile):
        cmd += ["--cookies-from-browser", f"chrome:{cdp_profile}"]
    else:
        cmd += ["--cookies-from-browser", "chrome"]
    return cmd


def download_vtt(url, language="ko"):
    """Download YouTube auto-generated subtitles as VTT"""
    import tempfile
    tmp_dir = tempfile.mkdtemp(prefix="vtt-")
    result = subprocess.run(
        _yt_base_cmd() + ["--write-auto-sub", "--sub-lang", language,
         "--skip-download", "--sub-format", "vtt",
         "-o", os.path.join(tmp_dir, "sub"), url],
        capture_output=True, text=True, timeout=60
    )
    vtt_path = os.path.join(tmp_dir, f"sub.{language}.vtt")
    if not os.path.exists(vtt_path):
        return None
    with open(vtt_path) as f:
        vtt_content = f.read()
    # Cleanup
    import shutil
    shutil.rmtree(tmp_dir, ignore_errors=True)
    return vtt_content


def parse_vtt(vtt_content):
    """Parse VTT to plain text, removing timestamps and duplicates"""
    lines = []
    seen = set()
    for line in vtt_content.split('\n'):
        line = line.strip()
        if not line or line.startswith('WEBVTT') or line.startswith('Kind:') or line.startswith('Language:'):
            continue
        if re.match(r'^\d{2}:\d{2}', line):
            continue
        clean = re.sub(r'<[^>]+>', '', line).strip()
        if clean and clean not in seen:
            seen.add(clean)
            lines.append(clean)
    return ' '.join(lines)


def parse_vtt_with_segments(vtt_content):
    """
    Parse VTT to segments with timestamps.
    Returns list of {time_str, start_sec, text} dicts.
    """
    segments = []
    lines = vtt_content.split('\n')
    i = 0

    while i < len(lines):
        line = lines[i].strip()

        # Match timestamp line: HH:MM:SS.mmm --> ...
        if re.match(r'^\d{2}:\d{2}:\d{2}\.\d{3}', line):
            # Extract start time
            time_match = re.match(r'^(\d{2}):(\d{2}):(\d{2})\.(\d{3})', line)
            if time_match:
                h, m, s, ms = map(int, time_match.groups())
                start_sec = h * 3600 + m * 60 + s + ms / 1000.0

                # Format time_str
                if h > 0:
                    time_str = f"{h}:{m:02d}:{s:02d}"
                else:
                    time_str = f"{m}:{s:02d}"

                # Collect text lines until blank line
                text_lines = []
                i += 1
                while i < len(lines):
                    text_line = lines[i].strip()
                    if not text_line:
                        break
                    # Strip HTML tags
                    clean = re.sub(r'<[^>]+>', '', text_line).strip()
                    if clean:
                        text_lines.append(clean)
                    i += 1

                # Deduplicate consecutive identical lines
                final_text = []
                for text in text_lines:
                    if not final_text or final_text[-1] != text:
                        final_text.append(text)

                if final_text:
                    segments.append({
                        "time_str": time_str,
                        "start_sec": start_sec,
                        "text": ' '.join(final_text)
                    })
            else:
                i += 1
        else:
            i += 1

    return segments


def correct_with_llm(text):
    """Correct VTT text using LLM Gateway"""
    from llm_gateway import call_llm

    task = """당신은 YouTube 자동생성 자막의 오타 교정 전문가입니다.
자동 음성 인식(ASR)으로 생성된 자막의 오타, 띄어쓰기 오류, 잘못 인식된 단어를 교정하세요.
규칙:
- 내용과 의미를 변경하지 마세요
- 원문의 구어체 표현과 문장 구조를 유지하세요
- 기술, 비즈니스, 외래어 등 전문 용어는 문맥에 맞게 교정하세요
- 교정된 텍스트만 출력하세요

다음 자막을 교정하세요:"""

    # Process in 3000-char chunks
    chunks = [text[i:i+3000] for i in range(0, len(text), 3000)]
    corrected_parts = []

    for chunk in chunks:
        result = call_llm(task=task, text=chunk, model="haiku")
        # Reject result if it looks like an API error (too short or rate-limit message)
        if result and len(result) > len(chunk) * 0.1 and "hit your limit" not in result:
            corrected_parts.append(result)
        else:
            corrected_parts.append(chunk)

    return ''.join(corrected_parts)


def process_video_vtt(video_id, url, language="ko", use_ocr=True):
    """Full pipeline: download VTT -> parse -> correct -> (optionally OCR) -> return"""
    vtt_content = download_vtt(url, language)
    if not vtt_content:
        return None

    raw_text = parse_vtt(vtt_content)
    if not raw_text:
        return None

    corrected_text = correct_with_llm(raw_text)

    # Parse segments with timestamps
    segments = parse_vtt_with_segments(vtt_content)

    # OCR 프레임 분석 (선택적)
    ocr_result = None
    if use_ocr:
        try:
            from ocr_pipeline import extract_text_from_video
            ocr_result = extract_text_from_video(url, language=language)
        except Exception as e:
            print(f"[ocr] 실패 (무시): {e}")

    return {
        "raw_text": raw_text,
        "corrected_text": corrected_text,
        "text_length": len(raw_text),
        "segments": segments,
        "ocr": ocr_result,  # None or {"frames_total": N, "frames_unique": M, "text": "..."}
    }
