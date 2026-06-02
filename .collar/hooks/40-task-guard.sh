#!/usr/bin/env bash
# collar task-guard hook — PostToolUse: Agent 위임 시 체크리스트 파일 강제 확인
#
# 목적: Agent() 호출 후 .collar/tasks/YYYYMMDD*.md 없으면 경고 주입
#       체크리스트 없이 완료 선언하는 패턴 방지 (CLAUDE.md 반복 위반 → 훅 강제)
#
# 동작:
#   PostToolUse + Agent: 오늘 task 파일 없으면 경고 (non-blocking, exit 0)
#   다른 이벤트: 즉시 종료

HOOK_DATA="$(cat)"

# ── 이벤트/도구명 파싱 ──────────────────────────────────────────────
PARSED="$(echo "$HOOK_DATA" | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    event = d.get('hook_event_name', '')
    tool  = d.get('tool_name', '')
    print(event + '|' + tool)
except:
    print('|')
" 2>/dev/null)"

EVENT_TYPE="${PARSED%%|*}"
TOOL_NAME="${PARSED##*|}"

# PostToolUse + Agent 이벤트만 처리
[ "$EVENT_TYPE" = "PostToolUse" ] || exit 0
[ "$TOOL_NAME" = "Agent" ]        || exit 0

# ── 오늘 task 파일 확인 ─────────────────────────────────────────────
HOOKS_DIR="$(cd "$(dirname "$0")" && pwd)"
COLLAR_DIR="$(dirname "$HOOKS_DIR")"
COLLAR_TASKS="$COLLAR_DIR/tasks"
TODAY="$(date +%Y%m%d)"

mkdir -p "$COLLAR_TASKS"

TASK_COUNT=$(find "$COLLAR_TASKS" -maxdepth 1 -name "${TODAY}*.md" 2>/dev/null | wc -l | tr -d ' ')

# task 파일 있으면 통과
[ "$TASK_COUNT" -gt 0 ] && exit 0

# ── 경고 출력 (Claude 컨텍스트에 system-reminder로 주입) ────────────
echo ""
echo "[TASK-GUARD] ⚠️  CLAUDE.md 2단계 위반 감지"
echo "[TASK-GUARD] Agent 위임이 실행됐으나 오늘 .collar/tasks/ 체크리스트 파일이 없습니다."
echo ""
echo "[TASK-GUARD] 지금 즉시 수행하세요:"
echo "  1. .collar/tasks/${TODAY}-HHMM-요약.md 파일 생성 (Write 도구)"
echo "  2. 각 완료 항목마다 [ ] → [x] 업데이트 (Edit 도구)"
echo "  3. 3단계+ 복잡한 작업이면: collar-conductor run \"태스크 설명\" --rounds 3"
echo ""
echo "[TASK-GUARD] 완료 선언 전 .collar/tasks/ 파일 경로 명시 의무."

exit 0
