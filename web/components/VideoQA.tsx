"use client";

import { useState, useEffect } from "react";
import { API_BASE } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Loader2, Send, MessageCircle, AlertCircle, TrendingUp, Briefcase, ExternalLink, ChevronDown, ChevronUp } from "lucide-react";
import { cn } from "@/lib/utils";

interface QAHistoryItem {
  id: number;
  question: string;
  answer: string;
  model: string;
  created_at: string;
}

interface QuotaStatus {
  user_id: string;
  quota_type: "free" | "premium";
  daily_used: number;
  daily_limit: number;
  quota_remaining: number;
  total_used: number;
}

interface VideoQAProps {
  videoId: string;
  userId?: string;
  language?: "ko" | "en";
}

export function VideoQA({ videoId, userId, language = "ko" }: VideoQAProps) {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<string | null>(null);
  const [history, setHistory] = useState<QAHistoryItem[]>([]);
  const [quota, setQuota] = useState<QuotaStatus | null>(null);

  const [loading, setLoading] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showHistory, setShowHistory] = useState(false);

  // AI 작업의뢰 상태
  const [showDelegate, setShowDelegate] = useState(false);
  const [delegatePrompt, setDelegatePrompt] = useState("");
  const [delegateModel, setDelegateModel] = useState("sonnet");
  const [delegateOutputType, setDelegateOutputType] = useState("markdown");
  const [delegating, setDelegating] = useState(false);
  const [delegateResult, setDelegateResult] = useState<{ taskId: string; aiTaskId: string } | null>(null);

  // 쿼터 상태 조회
  useEffect(() => {
    const fetchQuota = async () => {
      try {
        const headers: HeadersInit = {};
        if (userId) {
          headers["X-User-Id"] = userId;
        }
        const res = await fetch(`${API_BASE}/api/quota/status`, { headers });
        if (res.ok) {
          const data = await res.json();
          setQuota(data);
        }
      } catch (err) {
        console.error("쿼터 조회 실패:", err);
      }
    };

    fetchQuota();
    // 2분마다 쿼터 갱신
    const interval = setInterval(fetchQuota, 120000);
    return () => clearInterval(interval);
  }, [userId]);

  // 히스토리 조회
  const fetchHistory = async () => {
    if (loadingHistory) return;
    setLoadingHistory(true);
    try {
      const params = new URLSearchParams();
      if (userId) {
        params.append("user_id", userId);
      }
      const headers: HeadersInit = {};
      if (userId) {
        headers["X-User-Id"] = userId;
      }
      const res = await fetch(`${API_BASE}/api/qa/${videoId}/history?${params}`, { headers });
      if (res.ok) {
        const data = await res.json();
        setHistory(data.history || []);
      }
    } catch (err) {
      console.error("히스토리 조회 실패:", err);
    } finally {
      setLoadingHistory(false);
    }
  };

  useEffect(() => {
    if (showHistory) {
      fetchHistory();
    }
  }, [showHistory, videoId, userId]);

  const handleAsk = async () => {
    if (!question.trim()) return;
    if (!quota && !userId) {
      setError("사용자 정보를 확인할 수 없습니다.");
      return;
    }

    // 쿼터 체크
    if (quota?.quota_type === "free" && quota.quota_remaining <= 0) {
      setError("일일 무료 제한(10회)에 도달했습니다. 유료 업그레이드를 고려하세요.");
      return;
    }

    setLoading(true);
    setError(null);
    setAnswer(null);

    try {
      const headers: HeadersInit = {
        "Content-Type": "application/json",
      };
      if (userId) {
        headers["X-User-Id"] = userId;
      }

      const res = await fetch(`${API_BASE}/api/qa/${videoId}`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          question: question.trim(),
          language,
        }),
      });

      if (!res.ok) {
        const errorData = await res.json();
        setError(errorData.error || `요청 실패 (${res.status})`);
        if (errorData.message) {
          setError(errorData.message);
        }
        return;
      }

      const data = await res.json();
      setAnswer(data.answer);

      // 쿼터 업데이트
      if (data.quota_remaining !== undefined) {
        setQuota(prev => prev ? {
          ...prev,
          quota_remaining: data.quota_remaining,
          daily_used: Math.max(0, (prev.daily_limit === -1 ? 0 : prev.daily_limit) - data.quota_remaining),
        } : null);
      }

      // 질문 초기화
      setQuestion("");

      // 히스토리 갱신
      if (showHistory) {
        await fetchHistory();
      }
    } catch (err) {
      console.error("Q&A 요청 실패:", err);
      setError("API 연결 실패. 백엔드를 확인하세요.");
    } finally {
      setLoading(false);
    }
  };

  const handleDelegate = async () => {
    if (!delegatePrompt.trim()) return;
    setDelegating(true);
    setDelegateResult(null);
    try {
      const headers: HeadersInit = { "Content-Type": "application/json" };
      if (userId) headers["X-User-Id"] = userId;
      const res = await fetch(`${API_BASE}/api/ai-tasks`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          video_ids: [videoId],
          prompt: delegatePrompt.trim(),
          output_type: delegateOutputType,
          model: delegateModel,
        }),
      });
      if (!res.ok) throw new Error(`요청 실패 (${res.status})`);
      const data = await res.json();
      setDelegateResult({ taskId: data.task_id, aiTaskId: data.ai_task_id });
      setDelegatePrompt("");
    } catch (err) {
      console.error("AI작업의뢰 실패:", err);
    } finally {
      setDelegating(false);
    }
  };

  const quotaPercent = quota
    ? quota.daily_limit === -1
      ? 100
      : Math.max(0, (quota.quota_remaining / quota.daily_limit) * 100)
    : 0;

  return (
    <Card className="border-l-4 border-l-blue-500">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <MessageCircle className="w-5 h-5 text-blue-600" />
            <CardTitle className="text-lg">영상 Q&A</CardTitle>
          </div>
          {quota && (
            <Badge
              variant={quota.quota_remaining > 0 || quota.quota_type === "premium" ? "secondary" : "destructive"}
              className="text-xs"
            >
              <TrendingUp className="w-3 h-3 mr-1" />
              {quota.quota_type === "premium"
                ? "무제한"
                : `${quota.quota_remaining}/${quota.daily_limit}회 남음`}
            </Badge>
          )}
        </div>
        <CardDescription>
          이 영상의 내용을 기반으로 질문하면 AI가 답변해줍니다.
        </CardDescription>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* 쿼터 표시 */}
        {quota && quota.daily_limit !== -1 && (
          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs">
              <span className="text-muted-foreground">
                {quota.quota_type === "free" ? "무료" : "유료"}
              </span>
              <span className="font-medium">
                {quota.daily_used}/{quota.daily_limit}
              </span>
            </div>
            <div className="w-full h-2 bg-gray-200 rounded-full overflow-hidden">
              <div
                className={cn(
                  "h-full transition-all duration-300",
                  quota.quota_remaining > 0 ? "bg-blue-500" : "bg-red-500"
                )}
                style={{ width: `${100 - quotaPercent}%` }}
              />
            </div>
          </div>
        )}

        {/* 에러 메시지 */}
        {error && (
          <div className="p-3 bg-red-50 border border-red-200 rounded-lg flex gap-2">
            <AlertCircle className="w-4 h-4 text-red-600 shrink-0 mt-0.5" />
            <p className="text-xs text-red-700">{error}</p>
          </div>
        )}

        {/* Q&A 입력 */}
        <div className="space-y-2">
          <div className="flex gap-2">
            <Input
              placeholder="이 영상에 대해 질문하세요..."
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && !loading && handleAsk()}
              disabled={loading}
              className="flex-1"
            />
            <Button
              onClick={handleAsk}
              disabled={
                loading ||
                !question.trim() ||
                (quota?.quota_type === "free" && quota.quota_remaining <= 0)
              }
              size="sm"
              className="shrink-0"
            >
              {loading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Send className="w-4 h-4" />
              )}
            </Button>
          </div>
        </div>

        {/* 답변 */}
        {answer && (
          <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg space-y-2">
            <p className="text-xs font-medium text-blue-900">AI 답변</p>
            <p className="text-sm text-gray-800 leading-relaxed whitespace-pre-wrap">
              {answer}
            </p>
          </div>
        )}

        {/* 히스토리 토글 */}
        {history.length > 0 && (
          <div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowHistory(!showHistory)}
              className="w-full text-xs"
            >
              {showHistory ? "히스토리 접기" : `이전 질문 ${history.length}개 보기`}
            </Button>
          </div>
        )}

        {/* 히스토리 표시 */}
        {showHistory && (
          <div className="space-y-3 max-h-96 overflow-y-auto border-t pt-3">
            {loadingHistory ? (
              <div className="flex items-center justify-center py-4">
                <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" />
              </div>
            ) : history.length > 0 ? (
              history.map((item) => (
                <div key={item.id} className="space-y-2 p-3 bg-gray-50 rounded-lg">
                  <p className="text-xs font-medium text-gray-700">Q: {item.question}</p>
                  <p className="text-xs text-gray-600 leading-relaxed">{item.answer}</p>
                  <p className="text-xs text-muted-foreground">
                    {new Date(item.created_at).toLocaleString(language === "ko" ? "ko-KR" : "en-US")}
                  </p>
                </div>
              ))
            ) : (
              <p className="text-xs text-muted-foreground text-center py-4">
                이전 질문이 없습니다.
              </p>
            )}
          </div>
        )}
        {/* AI 작업의뢰 */}
        <div className="border-t pt-3">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => { setShowDelegate(!showDelegate); setDelegateResult(null); }}
            className="w-full flex items-center justify-between text-xs text-muted-foreground hover:text-foreground"
          >
            <span className="flex items-center gap-1.5">
              <Briefcase className="w-3.5 h-3.5" />
              AI 작업 의뢰
            </span>
            {showDelegate ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          </Button>

          {showDelegate && (
            <div className="mt-2 space-y-3">
              {/* 퀵 선택 버튼 */}
              <div className="flex flex-wrap gap-1.5">
                {[
                  { label: "핵심 인사이트", prompt: "영상에서 핵심 인사이트 5가지를 추출하고 각각 구체적으로 설명해주세요." },
                  { label: "블로그 포스트", prompt: "이 영상 내용을 바탕으로 독자가 공감할 수 있는 블로그 포스트를 작성해주세요." },
                  { label: "한 페이지 요약", prompt: "영상 내용을 핵심만 담아 한 페이지 분량으로 요약해주세요." },
                  { label: "강의 노트", prompt: "영상 내용을 개요, 주요 개념, 핵심 포인트 형식의 강의 노트로 정리해주세요." },
                ].map((q) => (
                  <Button
                    key={q.label}
                    variant="outline"
                    size="sm"
                    className="text-xs h-7"
                    onClick={() => setDelegatePrompt(q.prompt)}
                    disabled={delegating}
                  >
                    {q.label}
                  </Button>
                ))}
              </div>

              {/* 작업 지시 입력 */}
              <Textarea
                placeholder="AI에게 맡길 작업을 입력하세요. (예: 이 영상의 핵심 내용을 5가지로 요약해줘)"
                value={delegatePrompt}
                onChange={(e) => setDelegatePrompt(e.target.value)}
                disabled={delegating}
                rows={3}
                className="text-sm resize-none"
              />

              {/* 출력 형식 */}
              <div className="flex items-center gap-2">
                <span className="text-xs text-muted-foreground shrink-0">출력 형식:</span>
                <div className="flex gap-1">
                  {[
                    { value: "markdown", label: ".md 파일" },
                    { value: "txt", label: ".txt 파일" },
                    { value: "text", label: "텍스트만" },
                  ].map((opt) => (
                    <Button
                      key={opt.value}
                      variant={delegateOutputType === opt.value ? "secondary" : "outline"}
                      size="sm"
                      className="text-xs h-7"
                      onClick={() => setDelegateOutputType(opt.value)}
                      disabled={delegating}
                    >
                      {opt.label}
                    </Button>
                  ))}
                </div>
              </div>

              {/* 모델 선택 + 의뢰 버튼 */}
              <div className="flex items-center justify-between gap-2">
                <div className="flex gap-1">
                  {[
                    { value: "sonnet", label: "Sonnet (빠름)" },
                    { value: "opus", label: "Opus (정밀)" },
                    { value: "haiku", label: "Haiku (경량)" },
                  ].map((m) => (
                    <Button
                      key={m.value}
                      variant={delegateModel === m.value ? "secondary" : "outline"}
                      size="sm"
                      className="text-xs h-7"
                      onClick={() => setDelegateModel(m.value)}
                      disabled={delegating}
                    >
                      {m.label}
                    </Button>
                  ))}
                </div>
                <Button
                  size="sm"
                  onClick={handleDelegate}
                  disabled={delegating || !delegatePrompt.trim()}
                  className="shrink-0"
                >
                  {delegating ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
                  <span className="ml-1.5">의뢰</span>
                </Button>
              </div>

              {delegateResult && (
                <div className="p-2.5 bg-green-50 border border-green-200 rounded-lg flex items-center justify-between">
                  <p className="text-xs text-green-700">작업이 등록되었습니다.</p>
                  <a
                    href="/tasks"
                    className="flex items-center gap-1 text-xs text-green-700 font-medium hover:underline"
                  >
                    결과 보기 <ExternalLink className="w-3 h-3" />
                  </a>
                </div>
              )}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
