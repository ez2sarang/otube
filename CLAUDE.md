## ⚡ 최우선 규칙: COLLAR_WATCHDOG compact 지시

system-reminder에 아래 패턴이 보이면 **다른 모든 작업보다 먼저 `/compact`를 실행**하라.

```
COLLAR_WATCHDOG: [...] ctx X% (임계값 80%) 초과. 지금 즉시 /compact를 실행하라.
COLLAR_WATCHDOG: [...] 메시지 N개 도달. 지금 즉시 /compact를 실행하라.
```

- 사용자 요청이 있어도 `/compact` 먼저 실행 후 작업 재개
- 이 규칙은 예외 없음

---

# offline-thinking — 영상 AI 분석 파이프라인 (SaaS)

YouTube 등 영상에서 VTT/STT로 스크립트를 추출하고, 슬라이드를 캡처한 뒤,
내부 LLM 게이트웨이를 통해 사용자가 질의응답할 수 있는 멀티랭귀지 분석 서비스.
한국어·영어 지원, 유료화 예정 (AI 질의응답 권수 제한).

---

## 프로젝트 목적

> **"긴 영상의 분석·문서화·2차 AI 가공이 필요한 모든 사람"을 위한 오프라인 AI 분석 도구**

핵심 파이프라인:
1. 영상 URL (YouTube) → `yt-dlp` 다운로드
2. VTT 자막 우선 수집 → 없으면 `mlx-whisper` STT
3. 슬라이드 이미지 프레임 추출 (`ffmpeg`)
4. 수집 데이터 → LLM 게이트웨이 Q&A (`localhost:3100/PIN/llm-gateway`)

---

## 기술 스택

| 레이어 | 기술 |
|--------|------|
| STT | mlx-whisper (Mac M-시리즈 전용, CPU 배포 시 faster-whisper로 교체) |
| 다운로드 | yt-dlp |
| 오디오/영상 | ffmpeg |
| 백엔드 | FastAPI (port 9102) |
| LLM 게이트웨이 | paperCompany 내부 서비스, `localhost:3100/PIN/llm-gateway` |
| 유료화 | Stripe + Supabase Auth (1순위), cafe24결제 (대안) |
| 프론트 배포 | Vercel 고려 중 |
| 런타임 | Python 3.10+, venv |

---

## 프로젝트 구조

```
harness/          # 레포지토리 레벨 하네스 (운영 규칙)
  core/           # 헌법, 거버넌스
  roles/          # 역할 정의 (코더, 테스터, 리뷰어)
  workflows/      # 실행 루프, 파이프라인
  templates/      # 작업 지시서 템플릿
app/
  stt/            # STT 앱
    harness/      # 앱 전용 규약, 명세, 참고자료
    src/          # 소스 코드
    tests/        # 테스트
```

---

## 작업 시작 전 필수 사항

1. `AGENTS.md`의 Read Order에 따라 문서를 순서대로 읽을 것
2. `harness/core/constitution.md`의 Do/Don't를 숙지할 것
3. 현재 작업 대상 앱의 `harness/specs/`에서 기능 명세를 확인할 것

---

## 지금 집중해야 할 것 (우선순위 순)

✅ **[완료] SaaS 핵심 구현** (2026-05-15)
- Q&A API 라우터 (api/routers/qa.py)
- 사용 쿼터 DB + 미들웨어 (api/migrations/add_qa_quota.sql, api/auth.py)
- 프론트 Q&A 컴포넌트 (web/components/VideoQA.tsx)
- history 페이지에 Q&A 탭 통합
- Stripe 결제 스켈레톤 (api/stripe_payments.py)

1. **Stripe 결제 연동** — `.env`에 키 추가 후 stripe_payments.py 활성화
2. **Supabase Auth 통합** — JWT 검증로직 api/auth.py에서 활성화
3. **프론트 QA 히스토리 UI 개선** — 페이지네이션, 검색 추가
4. **영상별 인기 질문** — 같은 영상에서 많이 받은 Q&A 노출

---

## ⚠️ DB 스키마 격리 규칙 (반복 위반 주의)

**공유 Supabase:** `localhost:54322` (password: postgres, db: postgres)

이 DB는 여러 프로젝트가 공유한다. **이 프로젝트에서는 `offline_thinking` 스키마만 읽고 쓴다.**
다른 프로젝트의 스키마(`dho`, `bmw`, `cv`, `totalviewer`, `stt_analysis` 등)는 이유 불문 접근 금지.

**위반 사례 (2026-05-25):** `init_schema.sql`이 `stt_analysis`(레거시 이름)를 사용하고 있어 AI가 이를 현재 컨벤션으로 착각 → 신규 테이블을 `stt_analysis`에 생성 → 롤백 필요. 핵심 문제: 다른 프로젝트 스키마 무단 사용.

**절대 규칙:**
- 새 테이블/마이그레이션 → 반드시 `offline_thinking.*`
- `init_schema.sql`의 `stt_analysis`는 레거시 이름 — 따라 쓰지 말 것
- 스키마 불명확하면 추측 금지, 사용자에게 확인
- `offline_thinking` 스키마가 DB에 없으면 → `CREATE SCHEMA IF NOT EXISTS offline_thinking;` 후 작업 (귀찮다고 다른 스키마 사용 금지)

---

## 아키텍처 주의사항

### STT 환경 분기
- **로컬 개발 (Mac M-시리즈)**: `mlx-whisper` — 빠름
- **클라우드 배포 시**: `faster-whisper` 또는 브라우저 WebGPU 기반 Whisper로 교체 필요
- MLX는 Apple Silicon 전용 — CPU 서버에서 그대로 실행하면 매우 느림

### LLM 게이트웨이
- paperCompany 프로젝트에서 서비스 중: `localhost:3100/PIN/llm-gateway`
- API 문서: `localhost:3100/PIN/llm-gateway` (로컬에서만 접근 가능)
- 클라우드 배포 시 이 엔드포인트도 public URL 확보 필요

### 배포 전략
- 프론트: Vercel
- 백엔드 (FastAPI, port 9102): Railway / Fly.io 등 별도 서버
- LLM gateway: 로컬 public IP 또는 VPS 이전

---

## 코딩 규칙

- 코드 파일 500줄 이하
- 외부 API 의존 최소화, 로컬 퍼스트
- `requirements.txt`에 고정 버전 사용
- venv 안에서만 패키지 설치 (`pip install -r requirements.txt`)
- STT 구현체는 환경 변수 또는 설정으로 교체 가능하도록 추상화

---

## 검증 기준

현재: 직접 실행 후 결과 확인
- YouTube URL → STT 결과 텍스트 정상 출력
- LLM Q&A API 응답이 의도와 맞는지 주관적 판단

향후: pytest 자동화 테스트 도입 예정

---

## 성공 기준

1. 서비스 오픈 (실제 URL에서 동작)
2. Stripe 유료결제 완료 (AI 질의응답 권수 제한 + 결제 시 해제)
3. 한국어/영어 멀티 사용자가 찾는 서비스

---

## Skill routing

When the user's request matches an available skill, ALWAYS invoke it using the Skill
tool as your FIRST action. Do NOT answer directly, do NOT use other tools first.
The skill has specialized workflows that produce better results than ad-hoc answers.

Key routing rules:
- Product ideas, "is this worth building", brainstorming → invoke office-hours
- Bugs, errors, "why is this broken", 500 errors → invoke investigate
- Ship, deploy, push, create PR → invoke ship
- QA, test the site, find bugs → invoke qa
- Code review, check my diff → invoke review
- Update docs after shipping → invoke document-release
- Weekly retro → invoke retro
- Design system, brand → invoke design-consultation
- Visual audit, design polish → invoke design-review
- Architecture review → invoke plan-eng-review
- Save progress, checkpoint, resume → invoke checkpoint
- Code quality, health check → invoke health
