# 파이프라인 (Pipeline)

오디오/비디오 처리 작업의 표준 흐름.

## STT 파이프라인

```
입력 (URL 또는 파일)
    ↓
[다운로드] yt-dlp (URL인 경우)
    ↓
[오디오 추출] ffmpeg → WAV (16kHz mono)
    ↓
[STT 변환] mlx-whisper (large-v3-turbo)
    ↓
[후처리] 타임스탬프 정렬, 세그먼트 병합
    ↓
[문서화] 마크다운으로 정리
    ↓
출력 (transcript.md, transcript.json)
```

## 오디오 전처리 표준

- 샘플레이트: 16kHz (whisper 최적)
- 채널: mono
- 포맷: WAV
- 명령: `ffmpeg -i input -ar 16000 -ac 1 -f wav output.wav`
