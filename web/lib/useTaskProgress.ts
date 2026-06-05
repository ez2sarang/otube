"use client";
import { useState, useEffect, useCallback } from "react";
import { API_BASE, TaskStatus, TaskEvent } from "./types";

export function useTaskProgress() {
  const [taskId, setTaskId] = useState<string | null>(null);
  const [status, setStatus] = useState<TaskStatus>("idle");
  const [message, setMessage] = useState("");
  const [progress, setProgress] = useState(0);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!taskId) return;

    const es = new EventSource(`${API_BASE}/api/tasks/${taskId}/events`);

    es.onmessage = (e) => {
      try {
        const data: TaskEvent = JSON.parse(e.data);
        setStatus(data.status);
        setMessage(data.message);
        setProgress(data.progress);

        if (data.status === "done" && data.result) {
          setResult(data.result);
          es.close();
        }
        if (data.status === "error") {
          setError(data.error || data.message);
          es.close();
        }
      } catch {}
    };

    es.onerror = () => {
      es.close();
    };

    return () => es.close();
  }, [taskId]);

  const start = useCallback((id: string) => {
    setTaskId(id);
    setStatus("pending");
    setMessage("시작 중...");
    setProgress(0);
    setResult(null);
    setError(null);
  }, []);

  const reset = useCallback(() => {
    setTaskId(null);
    setStatus("idle");
    setMessage("");
    setProgress(0);
    setResult(null);
    setError(null);
  }, []);

  return { taskId, status, message, progress, result, error, start, reset };
}
