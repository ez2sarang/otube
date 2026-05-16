# AGENTS.md

AI 에이전트가 이 저장소에서 작업할 때 따라야 할 읽기 순서와 규칙.

## Read Order

1. `harness/core/constitution.md` → 헌법 (최우선 규칙)
2. `harness/core/governance.md` → 거버넌스 (운영 규칙)
3. `harness/roles/` → 현재 역할에 해당하는 문서
4. `harness/workflows/` → 실행 흐름
5. `app/{앱}/harness/docs/` → 앱별 프로덕트 센스
6. `app/{앱}/harness/specs/` → 기능 명세
7. `app/{앱}/harness/plans/` → 현재 진행 상황

## Current App

`app/stt` - 오프라인 STT(Speech-to-Text) 도구

## Working Rules

1. 헌법에 명시된 Do/Don't를 항상 준수
2. 작업 전 해당 앱의 specs 문서를 반드시 확인
3. 검증 기준을 통과해야 작업 완료로 간주
4. 모호한 지시는 사용자에게 확인 후 진행
5. 5번 반복 실패 시 멈추고 보고

## Entry Point

새 작업 시작 시: `app/stt/harness/plans/roadmap.md` 확인 후 다음 할 일 파악
