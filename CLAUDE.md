# offline-thinking

오프라인 AI 처리 도구 모음. 로컬에서 실행되는 STT, 텍스트 분석 등.

## 프로젝트 구조

```
harness/          # 레포지토리 레벨 하네스 (회사 취업규칙)
  core/           # 헌법, 거버넌스
  roles/          # 역할 정의 (코더, 테스터, 리뷰어)
  workflows/      # 실행 루프, 파이프라인
  templates/      # 작업 지시서 템플릿
app/              # 애플리케이션 레벨 하네스 (팀 프로젝트 매뉴얼)
  stt/            # STT 앱
    harness/      # 앱 전용 규약, 명세, 참고자료
    src/          # 소스 코드
    tests/        # 테스트
```

## 작업 시작 전 필수 사항

1. `AGENTS.md`의 Read Order에 따라 문서를 순서대로 읽을 것
2. `harness/core/constitution.md`의 Do/Don't를 숙지할 것
3. 현재 작업 대상 앱의 `harness/specs/`에서 기능 명세를 확인할 것

## 기술 스택

- Python 3.10+, venv
- mlx-whisper (STT)
- yt-dlp (다운로드)
- ffmpeg (오디오 처리)

## 규칙

- 코드 파일 500줄 이하
- 외부 API 의존 최소화, 로컬 퍼스트
- requirements.txt에 고정 버전 사용
- venv 안에서만 패키지 설치

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
