# 2026-06-05 DB 이관 + 배포 작업

## 요청 원문 요약
- 모든 생성 데이터(슬라이드 이미지, MD 파일 등) → DB로 관리
- GitHub에는 소스코드만 (data/, venv/ 등 제외)
- GitHub → Vercel 배포 (otube.pineai.dev)
- Supabase 프로덕션 생성 + 로컬 데이터 이관
- Cloudflare DNS + 접근제어 (비관리자 읽기전용)

## 체크리스트

### Phase 1: 데이터 DB 이관
- [ ] 1. stt_analysis.slides 테이블 생성 (image BYTEA 포함)
- [ ] 2. batch_slides_playlist.py → DB 저장 + 로컬 파일 삭제
- [ ] 3. api/routers/slides.py → DB에서 읽기
- [ ] 4. 기존 data/slides/ 데이터 → DB 마이그레이션 스크립트 실행

### Phase 2: GitHub 배포
- [ ] 5. .gitignore 강화 (data/, venv/ 등)
- [ ] 6. README.md 작성
- [ ] 7. GitHub repo 생성 (ez2sarang/otube) + push

### Phase 3: Supabase 프로덕션
- [ ] 8. Supabase 프로덕션 프로젝트 생성 (CDP)
- [ ] 9. 로컬 stt_analysis 스키마 → 프로덕션 마이그레이션

### Phase 4: Vercel + Cloudflare
- [ ] 10. Vercel 프로젝트 생성 + env 설정 (CDP)
- [ ] 11. Cloudflare DNS CNAME otube.pineai.dev (CDP)

## 진행 로그
- [19:30] 분석 완료, 구현 시작
