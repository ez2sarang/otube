"""백그라운드 태스크 관리 + SSE 스트리밍"""
from __future__ import annotations
import asyncio
import json
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


@dataclass
class TaskState:
    task_id: str
    status: TaskStatus = TaskStatus.PENDING
    message: str = ""
    progress: int = 0
    result: Optional[Any] = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    events: list = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def update(self, status: TaskStatus, message: str = "", progress: int = 0, result: Any = None, error: str = None):
        with self._lock:
            self.status = status
            self.message = message
            self.progress = progress
            if result is not None:
                self.result = result
            if error is not None:
                self.error = error
            event = {
                "status": status.value,
                "message": message,
                "progress": progress,
            }
            if status == TaskStatus.DONE and result is not None:
                event["result"] = result
            if status == TaskStatus.ERROR and error is not None:
                event["error"] = error
            self.events.append(event)


class TaskManager:
    def __init__(self):
        self._tasks: dict[str, TaskState] = {}
        self._lock = threading.Lock()

    def create_task(self) -> str:
        task_id = str(uuid.uuid4())[:8]
        with self._lock:
            self._tasks[task_id] = TaskState(task_id=task_id)
        return task_id

    def get_task(self, task_id: str) -> Optional[TaskState]:
        return self._tasks.get(task_id)

    def run_in_background(self, task_id: str, fn, *args, **kwargs):
        """함수를 백그라운드 스레드에서 실행"""
        def wrapper():
            task = self.get_task(task_id)
            if not task:
                return
            try:
                task.update(TaskStatus.RUNNING, "시작 중...")
                result = fn(task, *args, **kwargs)
                task.update(TaskStatus.DONE, "완료", 100, result=result)
            except Exception as e:
                task.update(TaskStatus.ERROR, str(e), error=str(e))

        thread = threading.Thread(target=wrapper, daemon=True)
        thread.start()

    async def stream_events(self, task_id: str):
        """SSE 이벤트 스트리밍"""
        task = self.get_task(task_id)
        if not task:
            yield f"data: {json.dumps({'error': 'Task not found'})}\n\n"
            return

        sent_count = 0
        while True:
            with task._lock:
                new_events = task.events[sent_count:]
                current_status = task.status

            for event in new_events:
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                sent_count += 1

            if current_status in (TaskStatus.DONE, TaskStatus.ERROR):
                break

            await asyncio.sleep(0.5)

    def cleanup_old(self, max_age_sec: int = 3600):
        now = time.time()
        with self._lock:
            to_remove = [
                tid for tid, t in self._tasks.items()
                if now - t.created_at > max_age_sec
            ]
            for tid in to_remove:
                del self._tasks[tid]


task_manager = TaskManager()
