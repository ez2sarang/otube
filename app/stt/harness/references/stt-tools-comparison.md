# STT 도구 비교 (2026-04-03 검증)

## Mac M시리즈 기준

| 도구 | 속도 (37분 영상) | 한국어 품질 | 설치 난이도 | 비고 |
|------|-----------------|------------|------------|------|
| **mlx-whisper** | ~2.5분 | 우수 | pip 한 줄 | Apple Silicon 네이티브 (MLX) |
| openai-whisper | ~10-15분 (추정) | 우수 | pip + torch | CPU 기반, GPU 미지원 (Mac) |
| faster-whisper | ~5-8분 (추정) | 우수 | pip + ctranslate2 | CPU 최적화 |

## 권장 모델

- `mlx-community/whisper-large-v3-turbo`: 속도와 품질의 최적 균형
- `mlx-community/whisper-large-v3`: 최고 품질, 속도 느림
- `mlx-community/whisper-small`: 빠르지만 한국어 품질 저하

## 실측 데이터

- 영상: "하네스 엔지니어링 따라하기" (37분 22초)
- 도구: mlx-whisper 0.4.2
- 모델: whisper-large-v3-turbo
- 변환 시간: 149초
- 세그먼트: 1,624개
- 텍스트: 15,360자
