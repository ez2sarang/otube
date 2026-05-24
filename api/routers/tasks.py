"""AI 작업 의뢰 + 결과 이력 관리"""
import json
import secrets
import subprocess

from typing import Optional

from fastapi import APIRouter
from fastapi.responses import Response
from pydantic import BaseModel

from db import execute, query, query_one
from services.task_manager import task_manager, TaskStatus

CLAUDE_BIN = "/opt/homebrew/bin/claude"


def _call_llm_cli(prompt: str, model: str = "sonnet", timeout: int = 600) -> Optional[str]:
    """claude CLI --print 모드로 LLM 직접 호출."""
    try:
        result = subprocess.run(
            [CLAUDE_BIN, "--print", "--model", model, "--no-session-persistence"],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        print(f"[llm_cli] 오류 (rc={result.returncode}) stdout={repr(result.stdout[:100])} stderr={repr(result.stderr[:400])}")
        return None
    except subprocess.TimeoutExpired:
        print(f"[llm_cli] 타임아웃 ({timeout}s)")
        return None
    except Exception as e:
        print(f"[llm_cli] 예외: {e}")
        return None

router = APIRouter(prefix="/api")


def ensure_tasks_table():
    try:
        execute("""
            CREATE TABLE IF NOT EXISTS stt_analysis.ai_tasks (
                id TEXT PRIMARY KEY,
                video_ids JSONB NOT NULL,
                video_titles JSONB DEFAULT '{}',
                prompt TEXT NOT NULL,
                output_type TEXT DEFAULT 'text',
                model TEXT DEFAULT 'sonnet',
                status TEXT DEFAULT 'pending',
                result_text TEXT,
                error_msg TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                completed_at TIMESTAMP WITH TIME ZONE
            )
        """)
        execute("ALTER TABLE stt_analysis.ai_tasks ADD COLUMN IF NOT EXISTS model TEXT DEFAULT 'sonnet'")
        execute("ALTER TABLE stt_analysis.ai_tasks ADD COLUMN IF NOT EXISTS parent_task_id TEXT")
    except Exception:
        pass


ensure_tasks_table()


class CreateTaskRequest(BaseModel):
    video_ids: list
    prompt: str
    output_type: str = "markdown"
    model: str = "sonnet"
    parent_task_id: Optional[str] = None


def _build_transcript(video_id: str, title: str, char_limit: int) -> str:
    """segments → 타임스탬프 포함 텍스트. 없으면 full_text 폴백."""
    row = query_one(
        "SELECT segments, corrected_text, full_text FROM stt_analysis.transcripts WHERE video_id = %s",
        (video_id,)
    )
    if not row:
        return ""
    segs = row.get("segments")
    if segs:
        parts = []
        total = 0
        for seg in segs:
            line = f"[{seg.get('time_str', '')}] {seg.get('text', '').strip()}"
            total += len(line)
            if total > char_limit:
                break
            parts.append(line)
        text = "\n".join(parts)
    else:
        raw = row.get("corrected_text") or row.get("full_text") or ""
        text = raw[:char_limit]
    return f"[영상: {title}]\n{text}" if text else ""


@router.post("/ai-tasks")
async def create_ai_task(req: CreateTaskRequest):
    """AI 작업 생성 + 백그라운드 실행"""
    task_id = task_manager.create_task()
    ai_task_id = f"ait_{secrets.token_hex(8)}"

    video_titles = {}
    for vid_id in req.video_ids[:5]:
        row = query_one("SELECT title FROM stt_analysis.videos WHERE id = %s", (vid_id,))
        if row:
            video_titles[vid_id] = row["title"]

    execute("""
        INSERT INTO stt_analysis.ai_tasks (id, video_ids, video_titles, prompt, output_type, model, status, parent_task_id)
        VALUES (%s, %s::jsonb, %s::jsonb, %s, %s, %s, 'running', %s)
    """, (ai_task_id, json.dumps(req.video_ids), json.dumps(video_titles), req.prompt, req.output_type, req.model, req.parent_task_id))

    def do_task(task, ai_id, video_ids, prompt, vt, model, parent_task_id):
        task.update(TaskStatus.RUNNING, "트랜스크립트 로딩 중...", 10)

        char_limit = 40000 if model == "opus" else 10000
        timeout = 600 if model == "opus" else 300

        # 후속 질문: 부모 결과를 컨텍스트로 사용
        parent_result = None
        if parent_task_id:
            parent_row = query_one(
                "SELECT result_text, prompt FROM stt_analysis.ai_tasks WHERE id = %s AND status='done'",
                (parent_task_id,)
            )
            if parent_row and parent_row["result_text"]:
                parent_result = parent_row["result_text"]

        contexts = []
        for vid_id in video_ids[:5]:
            title = vt.get(vid_id, vid_id)
            ctx = _build_transcript(vid_id, title, char_limit)
            if ctx:
                contexts.append(ctx)

        if not contexts and not parent_result:
            execute(
                "UPDATE stt_analysis.ai_tasks SET status='error', error_msg=%s, completed_at=NOW() WHERE id=%s",
                ("트랜스크립트를 찾을 수 없습니다.", ai_id)
            )
            return {"error": "트랜스크립트 없음"}

        task.update(TaskStatus.RUNNING, f"AI 처리 중... (모델: {model})", 40)

        if parent_result:
            # 후속 질문: 이전 분석 결과 + 트랜스크립트(있으면) 포함
            transcript_section = ""
            if contexts:
                combined = "\n\n---\n\n".join(contexts)
                transcript_section = f"\n\n**원본 트랜스크립트:**\n{combined}"
            system_task = f"""당신은 YouTube 영상 트랜스크립트 분석 전문가입니다.

**이전 분석 결과:**
{parent_result[:20000]}
{transcript_section}

위 이전 분석 결과를 참고하여 후속 질문에 답하세요.
마크다운 형식을 적극 활용하여 읽기 좋게 작성하세요."""
        else:
            combined = "\n\n---\n\n".join(contexts)
            system_task = f"""당신은 YouTube 영상 트랜스크립트 분석 전문가입니다.
다음은 분석 대상 영상의 트랜스크립트입니다 (타임스탬프 포함):

{combined}

위 내용을 바탕으로 사용자의 요청을 충실히 수행하세요.
마크다운 형식(제목, 목록, 강조, 코드블록 등)을 적극 활용하여 읽기 좋게 작성하세요.
구체적인 타임스탬프나 인용구가 있으면 함께 포함하세요."""

        result = _call_llm_cli(f"{system_task}\n\n{prompt}", model=model, timeout=timeout)

        if result is None:
            execute(
                "UPDATE stt_analysis.ai_tasks SET status='error', error_msg='LLM 처리 실패', completed_at=NOW() WHERE id=%s",
                (ai_id,)
            )
            return {"error": "LLM 실패"}

        execute("""
            UPDATE stt_analysis.ai_tasks
            SET status='done', result_text=%s, completed_at=NOW()
            WHERE id=%s
        """, (result, ai_id))

        task.update(TaskStatus.RUNNING, "완료", 100)
        return {"ai_task_id": ai_id, "done": True}

    task_manager.run_in_background(task_id, do_task, ai_task_id, req.video_ids, req.prompt, video_titles, req.model, req.parent_task_id)
    return {"task_id": task_id, "ai_task_id": ai_task_id}


@router.get("/ai-tasks")
async def list_ai_tasks():
    rows = query("""
        SELECT id, video_ids, video_titles, prompt, output_type, model, status,
               result_text, error_msg, created_at, completed_at, parent_task_id
        FROM stt_analysis.ai_tasks
        ORDER BY created_at DESC
        LIMIT 100
    """)
    result = []
    for row in rows:
        d = dict(row)
        d["created_at"] = d["created_at"].isoformat() if d["created_at"] else None
        d["completed_at"] = d["completed_at"].isoformat() if d["completed_at"] else None
        d["result_preview"] = d["result_text"][:400] if d["result_text"] else None
        d.pop("result_text", None)
        result.append(d)
    return result


class UpdateTaskRequest(BaseModel):
    parent_task_id: Optional[str] = None


@router.patch("/ai-tasks/{ai_task_id}")
async def update_ai_task(ai_task_id: str, req: UpdateTaskRequest):
    """parent_task_id 수정 (드래그&드롭 재배치용)"""
    execute(
        "UPDATE stt_analysis.ai_tasks SET parent_task_id=%s WHERE id=%s",
        (req.parent_task_id, ai_task_id)
    )
    return {"ok": True}


@router.get("/ai-tasks/{ai_task_id}")
async def get_ai_task(ai_task_id: str):
    row = query_one("""
        SELECT id, video_ids, video_titles, prompt, output_type, model, status,
               result_text, error_msg, created_at, completed_at
        FROM stt_analysis.ai_tasks WHERE id = %s
    """, (ai_task_id,))
    if not row:
        return Response(status_code=404)
    d = dict(row)
    d["created_at"] = d["created_at"].isoformat() if d["created_at"] else None
    d["completed_at"] = d["completed_at"].isoformat() if d["completed_at"] else None
    return d


@router.get("/ai-tasks/{ai_task_id}/download")
async def download_ai_task(ai_task_id: str):
    row = query_one(
        "SELECT output_type, result_text FROM stt_analysis.ai_tasks WHERE id = %s AND status='done'",
        (ai_task_id,)
    )
    if not row or not row["result_text"]:
        return Response(status_code=404)

    output_type = row["output_type"]
    content = row["result_text"]
    ext = "md" if output_type == "markdown" else "txt"
    media_type = "text/markdown" if output_type == "markdown" else "text/plain"
    filename = f"ai_task_{ai_task_id[-8:]}.{ext}"

    return Response(
        content=content.encode("utf-8"),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
