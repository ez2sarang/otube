"use client";

import { useEffect, useState, useRef } from "react";
import {
  CheckCircle2,
  XCircle,
  Loader2,
  Clock,
  FileImage,
  ChevronDown,
  X,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Button } from "@/components/ui/button";

interface VideoStatus {
  vid_id: string;
  title: string;
  status: "done" | "failed" | "in_progress" | "pending";
  slides: number;
}

interface BatchStatus {
  running: boolean;
  total: number;
  done: number;
  failed: number;
  in_progress: number;
  pending: number;
  total_slides: number;
  log_tail: string[];
  videos: VideoStatus[];
}

export function BatchJobMonitor() {
  const [status, setStatus] = useState<BatchStatus | null>(null);
  const [isOpen, setIsOpen] = useState(false);
  const [hasError, setHasError] = useState(false);
  const [countdownToClose, setCountdownToClose] = useState<number | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectAttemptsRef = useRef(0);

  useEffect(() => {
    // 초기 상태 로드
    fetch("http://localhost:9102/api/batch-slides/status")
      .then((res) => res.json())
      .then((data) => {
        setStatus(data);
        if (data.running) {
          setIsOpen(true);
        }
      })
      .catch(() => setHasError(true));

    // SSE 연결
    const connectSSE = () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }

      const eventSource = new EventSource(
        "http://localhost:9102/api/batch-slides/stream"
      );

      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as BatchStatus;
          setStatus(data);
          setHasError(false);
          reconnectAttemptsRef.current = 0;

          // 자동 종료 로직: 실행 중 아님 + 완료 상태
          if (!data.running && data.done + data.failed === data.total && data.total > 0) {
            setCountdownToClose(5);
          }
        } catch (error) {
          console.error("SSE parse error:", error);
        }
      };

      eventSource.onerror = () => {
        eventSource.close();
        reconnectAttemptsRef.current += 1;
        if (reconnectAttemptsRef.current < 3) {
          setTimeout(connectSSE, 2000);
        } else {
          setHasError(true);
        }
      };

      eventSourceRef.current = eventSource;
    };

    connectSSE();

    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, []);

  // 자동 종료 카운트다운
  useEffect(() => {
    if (countdownToClose === null) return;
    if (countdownToClose <= 0) {
      setIsOpen(false);
      setCountdownToClose(null);
      return;
    }
    const timer = setTimeout(() => {
      setCountdownToClose(countdownToClose - 1);
    }, 1000);
    return () => clearTimeout(timer);
  }, [countdownToClose]);

  if (!status) {
    return null;
  }

  const progress = status.total > 0 ? (status.done / status.total) * 100 : 0;
  const isRunning = status.running;

  return (
    <>
      {/* 플로팅 버튼 */}
      <button
        onClick={() => setIsOpen(true)}
        className={`fixed bottom-6 right-6 w-14 h-14 rounded-full shadow-lg flex items-center justify-center transition-all ${
          isRunning
            ? "bg-blue-500 hover:bg-blue-600 animate-pulse"
            : "bg-zinc-700 hover:bg-zinc-800"
        }`}
      >
        <div className="flex items-center justify-center relative">
          {isRunning && (
            <div className="absolute inset-0 rounded-full bg-blue-500/20 animate-pulse" />
          )}
          <FileImage className="w-6 h-6 text-white relative z-10" />
          {status.total > 0 && (
            <span className="absolute -top-2 -right-2 bg-white text-blue-600 text-xs font-bold w-5 h-5 rounded-full flex items-center justify-center">
              {status.done}
            </span>
          )}
        </div>
      </button>

      {/* 슬라이드 오버 패널 */}
      {isOpen && (
        <>
          {/* 배경 오버레이 */}
          <div
            className="fixed inset-0 bg-black/30 z-40 transition-opacity"
            onClick={() => setIsOpen(false)}
          />

          {/* 패널 */}
          <div className="fixed right-0 top-0 h-full w-[420px] bg-white dark:bg-zinc-900 shadow-2xl z-50 flex flex-col overflow-hidden animate-in slide-in-from-right">
            {/* 헤더 */}
            <div className="flex items-center justify-between p-4 border-b border-zinc-200 dark:border-zinc-800">
              <div className="flex items-center gap-2">
                <FileImage className="w-5 h-5 text-blue-600" />
                <h2 className="font-semibold">배치 작업</h2>
                {isRunning && (
                  <Badge variant="default" className="ml-2">
                    실행 중
                  </Badge>
                )}
              </div>
              <button
                onClick={() => setIsOpen(false)}
                className="p-1 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* 콘텐츠 */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {/* 진행 상황 바 */}
              <div>
                <div className="flex justify-between items-center mb-2">
                  <span className="text-sm font-medium">진행 상황</span>
                  <span className="text-xs text-muted-foreground">
                    {status.done} / {status.total}
                  </span>
                </div>
                <Progress value={progress} className="h-2" />
              </div>

              {/* 통계 */}
              <div className="grid grid-cols-4 gap-2">
                <div className="bg-green-50 dark:bg-green-900/20 rounded p-2 text-center">
                  <div className="flex justify-center mb-1">
                    <CheckCircle2 className="w-4 h-4 text-green-600" />
                  </div>
                  <div className="text-lg font-bold text-green-700 dark:text-green-400">
                    {status.done}
                  </div>
                  <div className="text-xs text-green-600 dark:text-green-400">
                    완료
                  </div>
                </div>

                <div className="bg-red-50 dark:bg-red-900/20 rounded p-2 text-center">
                  <div className="flex justify-center mb-1">
                    <XCircle className="w-4 h-4 text-red-600" />
                  </div>
                  <div className="text-lg font-bold text-red-700 dark:text-red-400">
                    {status.failed}
                  </div>
                  <div className="text-xs text-red-600 dark:text-red-400">
                    실패
                  </div>
                </div>

                <div className="bg-blue-50 dark:bg-blue-900/20 rounded p-2 text-center">
                  <div className="flex justify-center mb-1">
                    <Loader2 className="w-4 h-4 text-blue-600 animate-spin" />
                  </div>
                  <div className="text-lg font-bold text-blue-700 dark:text-blue-400">
                    {status.in_progress}
                  </div>
                  <div className="text-xs text-blue-600 dark:text-blue-400">
                    진행
                  </div>
                </div>

                <div className="bg-gray-50 dark:bg-gray-900/20 rounded p-2 text-center">
                  <div className="flex justify-center mb-1">
                    <Clock className="w-4 h-4 text-gray-600" />
                  </div>
                  <div className="text-lg font-bold text-gray-700 dark:text-gray-400">
                    {status.pending}
                  </div>
                  <div className="text-xs text-gray-600 dark:text-gray-400">
                    대기
                  </div>
                </div>
              </div>

              {/* 비디오 테이블 */}
              <div>
                <h3 className="text-sm font-semibold mb-2">비디오</h3>
                <div className="space-y-1 max-h-64 overflow-auto border border-zinc-200 dark:border-zinc-800 rounded">
                  {status.videos.length === 0 ? (
                    <div className="p-3 text-xs text-muted-foreground text-center">
                      비디오 없음
                    </div>
                  ) : (
                    status.videos.map((video) => (
                      <div
                        key={video.vid_id}
                        className="flex items-center gap-2 p-2 border-b border-zinc-100 dark:border-zinc-800 last:border-0 hover:bg-zinc-50 dark:hover:bg-zinc-800/50"
                      >
                        <div className="w-4 h-4 flex-shrink-0">
                          {video.status === "done" && (
                            <CheckCircle2 className="w-4 h-4 text-green-600" />
                          )}
                          {video.status === "failed" && (
                            <XCircle className="w-4 h-4 text-red-600" />
                          )}
                          {video.status === "in_progress" && (
                            <Loader2 className="w-4 h-4 text-blue-600 animate-spin" />
                          )}
                          {video.status === "pending" && (
                            <Clock className="w-4 h-4 text-gray-400" />
                          )}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="text-xs font-medium truncate">
                            {video.title}
                          </div>
                          <div className="text-xs text-muted-foreground">
                            {video.slides} 슬라이드
                          </div>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>

              {/* 로그 */}
              <div>
                <h3 className="text-sm font-semibold mb-2">로그</h3>
                <div className="bg-zinc-950 text-zinc-300 font-mono text-xs p-3 rounded overflow-auto max-h-32 border border-zinc-800">
                  {status.log_tail.length === 0 ? (
                    <div className="text-zinc-500">로그 없음</div>
                  ) : (
                    status.log_tail.map((line, idx) => (
                      <div key={idx} className="break-words">
                        {line}
                      </div>
                    ))
                  )}
                </div>
              </div>

              {/* 자동 종료 알림 */}
              {countdownToClose !== null && (
                <div className="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded p-3 text-sm text-green-700 dark:text-green-400">
                  완료되었습니다. {countdownToClose}초 후 창이 닫힙니다.
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </>
  );
}
