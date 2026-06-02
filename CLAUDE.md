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

## 요청사항 체크리스트 의무 관리 (모든 프로젝트 공통)

**요청에 2개 이상의 독립 작업** 또는 **다단계 구현**이 포함되면, 작업 시작 전 반드시 아래 절차를 따른다.

### 1단계: 요청 분석 표 (작업 시작 전 사용자에게 보여주기)

요청을 받으면 먼저 **표로 정리**해서 누락 없이 확인하라:

| # | 요청 항목 | 구현 방법 | 대상 위치 | 완료 |
|---|----------|---------|---------|------|
| 1 | ...      | ...     | ...     | [ ] |

### 2단계: 작업 추적 문서 생성

`.collar/tasks/` 가 있으면 거기에, 없으면 `.tasks/` 디렉토리에 `YYYYMMDD-HHMM-<요약>.md` 파일 생성:

```
# [날짜] 요청 요약

## 요청 원문 요약
[사용자 요청 핵심 내용]

## 체크리스트
- [ ] 항목 1: 상세 설명
- [ ] 항목 2: 상세 설명

## 구현 계획
| # | 항목 | 방법 | 파일/위치 |
|---|------|------|---------|

## 진행 로그
- [HH:MM] 항목 1 완료
```

### 3단계: 진행 중 체크

각 항목 완료 시마다 파일의 `[ ]` → `[x]` 업데이트. **파일 수정 없이 머릿속으로만 체크 금지.**

### 4단계: 완료 선언 조건

- 모든 `[ ]` → `[x]` 전환 확인 후에만 완료 선언
- 완료 선언 시 체크리스트 파일 경로 명시
- 미완료 항목이 남아있으면 완료 선언 불가

### 단일 항목 요청 예외

한 줄 요청이나 명확한 단일 작업은 문서 생성 생략 가능. 단, 작업 중 추가 항목이 발견되면 즉시 문서 생성.

## 규칙 추가 전 실행 가능성 검증 의무 (모든 프로젝트 공통)

CLAUDE.md에 새로운 자동화 규칙·훅 동작·슬래시 커맨드를 추가하기 전에 반드시 검증하라.

**검증 질문:**
1. 이 동작을 Claude(AI 모델)가 직접 실행할 수 있는가?
2. 아니면 Claude Code(클라이언트)가 실행해야 하는가?
3. 훅 스크립트(bash)가 실행해야 하는가?

**금지 패턴:**
- Claude가 `/compact`, `/clear` 등 슬래시 커맨드를 직접 실행하게 하는 규칙 → 구조상 불가
- 훅 출력 메시지만으로 Claude가 자동으로 시스템 명령을 실행하게 하는 규칙

**올바른 접근:**
- Claude가 직접 못 하는 것 → Claude Code 네이티브 설정(settings.json)으로 처리
- 예: `autoCompactEnabled: true` (Claude Code가 compact 실행)

실패 사례: `/compact` 자동 실행 규칙을 CLAUDE.md에 2번 추가했다가 2번 revert (2026-05-29)

---

## 반복 위반 → 강제 전환 원칙 (모든 프로젝트 공통)

같은 규칙이 2회 이상 위반되면 텍스트 규칙은 효과 없음으로 판정하고 즉시 강제 수단으로 전환한다.

| 위반 횟수 | 대응 |
|----------|------|
| 1회 | CLAUDE.md에 텍스트 규칙 추가 |
| 2회 | 훅 스크립트(~/.claude/hooks/)로 자동 차단 |
| 3회+ | 훅 차단 + 사용자에게 즉시 보고 의무 |

근거: socialMakeit 세션 분석 결과, CDP 탭 닫힘 규칙이 텍스트로 명시됐음에도 6회+ 반복 위반됨 (2026-05-29 분석).


## UI/프론트엔드 변경 시 브라우저 실제 확인 의무

UI 컴포넌트, CSS, 레이아웃, 차트, 테이블 등 시각적 변경 후 반드시 브라우저 실제 렌더링 확인.
스크린샷: `uv run --with patchright python3 ~/.collar/bin/browser-test.py http://localhost:<PORT> /tmp/ui-check.png --cdp=http://localhost:9222`
코드만 보고 완료 선언 금지. 근거: investments revert 사고 (2026-05-29).

## 외부 API 공식 문서 우선 원칙

외부 API 사용 코드 작성 전 반드시 공식 문서 확인 (파라미터, 응답 형식, 인증).
추측으로 API 구현 금지. 근거: KIS API 스펙 미확인 → 연쇄 수정 4회 (investments 2026-05-29).

## 모듈 구조 변경 시 영향도 분석 의무

함수 이동, 파일 분리 등 구조 변경 시 반드시 import 영향도 먼저 분석:
`grep -r "from.*모듈명\|import.*심볼명"` 로 전체 참조 확인 후 변경.
영향도 미분석 후 변경 금지. 근거: investments 모듈 분리 오류 (2026-05-29).

## Opus 강제 트리거 실제 준수

근거/소스레벨/심도/전략/분석/왜 키워드가 있는 요청은 즉시 Opus 사용.
Sonnet으로 시작 후 재요청 받는 패턴 금지. 근거: investments 분석 품질 저하 사고 (2026-05-29).


## "불가능" 허위 선언 금지 원칙

증거 없이 "불가능합니다", "할 수 없습니다", "사용자가 직접 해야 합니다" 선언 절대 금지.
근거: socialMakeit 세션 분석 — 42개 자기모순, 8개 CRITICAL (2026-05-29).

**"불가능" 주장 전 반드시:**
1. 실제 시도 (Bash/도구 실행) — 시도 없이 불가능 선언 금지
2. 오류 메시지 정확히 인용 — 실제 에러 텍스트 첨부
3. 대안 1개 이상 제시 후 사용자 확인

**금지 패턴:**
- "CDP 자동화 불가능합니다" (시도 없이) → 1~4턴 후 실제 성공하는 패턴 반복됨
- "보안 SDK가 차단합니다" → 우회 방법 시도 없이 포기 선언
- "사용자가 직접 해야 합니다" → AI가 시도도 안 하고 떠넘기기

**진행 상황 보고 의무:**
- "완료됐습니다" → 반드시 도구 결과(Bash 출력, HTTP 상태코드 등) 첨부
- "확인했습니다" → 반드시 Read/Bash 실행 결과 인용

## 복잡한 작업 오케스트레이션 — collar-conductor 필수

**3단계 이상 멀티스텝 작업**은 직접 Agent() 호출 금지. `collar-conductor`를 통해 Executor→Verifier 루프로 실행:

```bash
collar-conductor run "태스크 설명" --rounds 3
collar-conductor run "태스크 설명" --rounds 5 --model complex
collar-conductor log    # 이력 확인
```

collar-conductor가 자동으로:
1. **Executor 에이전트** → 실제 코드 구현 (Sonnet)
2. **Verifier 에이전트** → 독립 검증 (Sonnet)
3. `NEEDS_WORK` 시 재작업 지시 (최대 --rounds 횟수)
4. `APPROVED` 시 완료 선언 + 로그 기록

| 작업 유형 | 방법 |
|---------|------|
| 단일 파일 수정 | 직접 Edit/Write |
| 2단계 이하 | Agent() + 체크리스트 파일 |
| 3단계+ / 복잡한 구현 | `collar-conductor run` 필수 |

**절대 금지:** 체크리스트 파일 없이 Agent() 호출 (훅 40-task-guard.sh가 감지·경고)

---
