# STT CLI 기능 명세

## 명령어

```bash
python -m app.stt.src.transcribe <입력> [옵션]
```

## 입력

- YouTube URL: `https://youtu.be/...` 또는 `https://www.youtube.com/watch?v=...`
- 로컬 파일: `.mp3`, `.wav`, `.m4a`, `.mp4`, `.webm`

## 옵션

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--lang` | `ko` | 언어 코드 |
| `--model` | `mlx-community/whisper-large-v3-turbo` | Whisper 모델 |
| `--output` | `./output/` | 출력 디렉토리 |
| `--format` | `md` | 출력 포맷 (md, txt, json, srt) |
| `--timestamps` | `true` | 타임스탬프 포함 여부 |

## 출력 파일

| 파일 | 설명 |
|------|------|
| `transcript.md` | 마크다운 정리본 |
| `transcript.json` | 세그먼트별 타임스탬프 포함 JSON |
| `transcript.srt` | 자막 파일 (선택) |
| `transcript_raw.txt` | 원본 텍스트 |

## 검증 기준

- [ ] YouTube URL 입력 시 오디오 다운로드 성공
- [ ] 로컬 파일 입력 시 WAV 변환 성공
- [ ] 한국어 텍스트 추출 정확도 체감 80% 이상
- [ ] 타임스탬프가 실제 오디오와 ±3초 이내
- [ ] 출력 파일이 지정된 디렉토리에 생성됨
- [ ] 37분 영상 처리 시간 5분 이내 (M시리즈 Mac)
