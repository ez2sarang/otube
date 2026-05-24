"""LLM Gateway client - delegates to plugin-llm-gateway at localhost:3100"""
from __future__ import annotations
import base64
import json
import os
import threading
import urllib.request
import uuid
from pathlib import Path

GATEWAY_URL = "http://localhost:3100/api/plugins/llm-gateway/webhooks/process"
_API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")
CALLBACK_BASE = f"{_API_BASE}/internal/llm-callback"

_pending: dict[str, tuple[threading.Event, list]] = {}
_lock = threading.Lock()


def register_pending(request_id: str) -> tuple[threading.Event, list]:
    event = threading.Event()
    result: list = []
    with _lock:
        _pending[request_id] = (event, result)
    return event, result


def handle_callback(request_id: str, data: dict) -> None:
    with _lock:
        entry = _pending.pop(request_id, None)
    if entry:
        event, result = entry
        result.append(data)
        event.set()


_MODEL_MAP = {
    "haiku": "claude-haiku-4-5-20251001",
    "sonnet": "claude-sonnet-4-5",
    "opus": "claude-opus-4-5",
}


_CLAUDE_BIN = os.getenv("CLAUDE_BIN", "/opt/homebrew/bin/claude")


def _call_anthropic_sdk(task: str, text: str, model: str) -> str | None:
    """Direct Claude CLI fallback when gateway is unavailable."""
    import subprocess
    resolved = _MODEL_MAP.get(model.lower(), model)
    prompt = f"[TASK]\n{task}\n\n[INPUT]\n{text}"
    try:
        result = subprocess.run(
            [_CLAUDE_BIN, "--print", "-", "--output-format", "text", "--model", resolved],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=120,
            env={**os.environ},
        )
        if result.returncode == 0:
            return result.stdout.strip()
        print(f"[llm_gateway] CLI 폴백 실패 (exit {result.returncode}): {result.stderr[:200]}")
    except Exception as e:
        print(f"[llm_gateway] CLI 폴백 예외: {e}")
    return None


def call_llm(
    task: str,
    text: str,
    model: str = "haiku",
    think: bool = False,
    timeout: int = 8,
) -> str | None:
    """POST to LLM gateway and block until callback arrives. Falls back to Anthropic SDK on failure."""
    request_id = str(uuid.uuid4())
    callback_url = f"{CALLBACK_BASE}/{request_id}"

    event, result = register_pending(request_id)

    payload = json.dumps({
        "requestId": request_id,
        "model": model,
        "task": task,
        "text": text,
        "think": think,
        "callbackUrl": callback_url,
    }).encode()

    req = urllib.request.Request(
        GATEWAY_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    gateway_ok = False
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status < 300:
                gateway_ok = True
    except Exception as e:
        print(f"[llm_gateway] 게이트웨이 요청 실패, SDK 폴백 사용: {e}")

    if not gateway_ok:
        with _lock:
            _pending.pop(request_id, None)
        return _call_anthropic_sdk(task, text, model)

    if not event.wait(timeout=timeout):
        with _lock:
            _pending.pop(request_id, None)
        print(f"[llm_gateway] 타임아웃 ({timeout}s), SDK 폴백 사용: {request_id}")
        return _call_anthropic_sdk(task, text, model)

    if result and result[0].get("status") == "completed":
        return result[0].get("output")
    print(f"[llm_gateway] 게이트웨이 오류, SDK 폴백 사용: {result[0].get('error') if result else 'no result'}")
    with _lock:
        _pending.pop(request_id, None)
    return _call_anthropic_sdk(task, text, model)


def call_llm_with_image(
    task: str,
    image_path: str,
    ocr_text: str = "",
    model: str = "claude-haiku-4-5-20251001",
    timeout: int = 60,
) -> str | None:
    """
    Send image + OCR text to LLM for analysis.

    Tries plugin-llm-gateway first (with base64 images field).
    Falls back to direct anthropic SDK call if gateway returns non-202.
    """
    # Try gateway first
    request_id = str(uuid.uuid4())
    callback_url = f"{CALLBACK_BASE}/{request_id}"

    ext = Path(image_path).suffix.lstrip(".").lower()
    media_type = f"image/{'jpeg' if ext in ('jpg', 'jpeg') else ext}"
    with open(image_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()

    event, result = register_pending(request_id)

    payload = json.dumps({
        "requestId": request_id,
        "model": model,
        "task": task,
        "text": ocr_text,
        "images": [{"media_type": media_type, "data": img_b64}],
        "callbackUrl": callback_url,
    }).encode()

    req = urllib.request.Request(
        GATEWAY_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    gateway_ok = False
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 202:
                gateway_ok = True
    except Exception:
        pass

    if gateway_ok:
        if event.wait(timeout=timeout):
            if result and result[0].get("status") == "completed":
                return result[0].get("output")
        with _lock:
            _pending.pop(request_id, None)
    else:
        with _lock:
            _pending.pop(request_id, None)

    # Fallback: direct anthropic SDK call
    return _call_claude_vision(task, image_path, img_b64, media_type, ocr_text, model)


def _call_claude_vision(
    task: str,
    image_path: str,
    img_b64: str,
    media_type: str,
    ocr_text: str,
    model: str,
) -> str | None:
    try:
        import anthropic
        client = anthropic.Anthropic()
        text_content = f"{task}\n\n[OCR 텍스트]\n{ocr_text}" if ocr_text else task
        response = client.messages.create(
            model=model,
            max_tokens=1024,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": img_b64}},
                    {"type": "text", "text": text_content},
                ],
            }],
        )
        return response.content[0].text if response.content else None
    except Exception as e:
        print(f"[llm_gateway] vision fallback 실패: {e}")
        return None
