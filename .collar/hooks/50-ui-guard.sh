#!/usr/bin/env bash
# collar ui-guard hook — PreToolUse: UI 파일 수정 전 스크린샷 사전 확인 강제
#
# 목적: UI 파일 Write/Edit 시 최근 스크린샷(10분 이내) 없으면 경고
#       "요청 → 즉시 코드 수정" 패턴 방지 (investments 2026-06-02 분석)
#
# 동작:
#   PreToolUse + Write/Edit: UI 파일이고 최근 스크린샷 없으면 경고 (non-blocking, exit 0)
#   다른 이벤트/파일: 즉시 종료

HOOK_DATA="$(cat)"

# ── 이벤트/도구명 파싱 ──────────────────────────────────────────────
PARSED="$(echo "$HOOK_DATA" | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    event = d.get('hook_event_name', '')
    tool  = d.get('tool_name', '')
    inp   = d.get('tool_input', {})
    fp    = inp.get('file_path', '')
    print(event + '|' + tool + '|' + fp)
except:
    print('||')
" 2>/dev/null)"

EVENT_TYPE="${PARSED%%|*}"
REST="${PARSED#*|}"
TOOL_NAME="${REST%%|*}"
FILE_PATH="${REST#*|}"

# PreToolUse + Write/Edit 이벤트만 처리
[ "$EVENT_TYPE" = "PreToolUse" ] || exit 0
{ [ "$TOOL_NAME" = "Write" ] || [ "$TOOL_NAME" = "Edit" ]; } || exit 0

# ── UI 파일 감지 ─────────────────────────────────────────────────────
IS_UI=0
case "$FILE_PATH" in
    *.html|*.tsx|*.jsx|*.vue|*.css|*.scss|*.sass)
        IS_UI=1 ;;
    */static/*|*/frontend/src/*|*/templates/*)
        IS_UI=1 ;;
    */components/*|*/pages/*|*/app/*)
        # Next.js / React 파일이면
        case "$FILE_PATH" in *.ts|*.js|*.tsx|*.jsx) IS_UI=1 ;; esac
        ;;
esac

[ "$IS_UI" -eq 1 ] || exit 0

# ── 최근 스크린샷 확인 (10분 이내) ──────────────────────────────────
RECENT_SHOT=$(find /tmp -maxdepth 1 -name "*.png" -mmin -10 2>/dev/null | head -1)

[ -n "$RECENT_SHOT" ] && exit 0

# ── 경고 출력 ────────────────────────────────────────────────────────
echo ""
echo "[UI-GUARD] ⚠️  UI 파일 수정 전 브라우저 확인 누락"
echo "[UI-GUARD] 대상: $FILE_PATH"
echo ""
echo "[UI-GUARD] 수정 전 반드시 현재 상태를 확인하세요:"
echo "  # 포트는 project-facts.md 또는 .env에서 확인"
echo "  uv run --with patchright python3 ~/.collar/bin/browser-test.py \\"
echo "    http://localhost:<PORT>/<PATH> /tmp/ui-before.png --cdp=http://localhost:9222"
echo ""
echo "[UI-GUARD] 확인 없이 수정하면 어디가 깨졌는지 모른 채 코드만 반복 수정하게 됩니다."
echo "[UI-GUARD] 스크린샷 촬영 후 수정하세요. (non-blocking: 수정은 계속됩니다)"

exit 0
