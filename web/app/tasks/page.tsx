"use client";
import { useState, useEffect, useCallback } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Briefcase, Download, Copy, Loader2, Clock, Check, FileText,
  AlertCircle, RefreshCw, MessageSquarePlus, Send, CornerDownRight, X, GripVertical,
  ExternalLink,
} from "lucide-react";

interface AiTask {
  id: string;
  video_ids: string[];
  video_titles: Record<string, string>;
  prompt: string;
  output_type: string;
  model: string;
  status: "pending" | "running" | "done" | "error";
  result_preview: string | null;
  error_msg: string | null;
  created_at: string;
  completed_at: string | null;
  parent_task_id: string | null;
}

interface FollowUpState {
  prompt: string;
  model: string;
  submitting: boolean;
}

function fmtTime(iso: string) {
  return new Date(iso).toLocaleString("ko-KR", {
    month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit",
  });
}

const OUTPUT_TYPE_LABEL: Record<string, string> = {
  markdown: ".md 파일",
  txt: ".txt 파일",
  text: "텍스트",
};

const MODEL_OPTIONS = [
  { value: "sonnet", label: "Sonnet (빠름)" },
  { value: "opus", label: "Opus (정밀)" },
  { value: "haiku", label: "Haiku (경량)" },
];

const mdComponents = {
  h1: ({ children }: React.ComponentProps<"h1">) => <h1 className="text-xl font-bold mt-5 mb-2 pb-1 border-b">{children}</h1>,
  h2: ({ children }: React.ComponentProps<"h2">) => <h2 className="text-lg font-semibold mt-4 mb-1.5 pb-1 border-b border-muted">{children}</h2>,
  h3: ({ children }: React.ComponentProps<"h3">) => <h3 className="text-base font-semibold mt-3 mb-1">{children}</h3>,
  h4: ({ children }: React.ComponentProps<"h4">) => <h4 className="text-sm font-semibold mt-2 mb-1">{children}</h4>,
  p: ({ children }: React.ComponentProps<"p">) => <p className="text-sm leading-relaxed mb-2">{children}</p>,
  ul: ({ children }: React.ComponentProps<"ul">) => <ul className="list-disc pl-5 mb-2 space-y-0.5 text-sm">{children}</ul>,
  ol: ({ children }: React.ComponentProps<"ol">) => <ol className="list-decimal pl-5 mb-2 space-y-0.5 text-sm">{children}</ol>,
  li: ({ children }: React.ComponentProps<"li">) => <li className="text-sm leading-relaxed">{children}</li>,
  blockquote: ({ children }: React.ComponentProps<"blockquote">) => (
    <blockquote className="border-l-4 border-primary/30 pl-3 py-0.5 my-2 text-sm text-muted-foreground italic bg-muted/30 rounded-r">{children}</blockquote>
  ),
  code: ({ inline, children, ...props }: React.ComponentProps<"code"> & { inline?: boolean }) =>
    inline
      ? <code className="bg-muted px-1 py-0.5 rounded text-xs font-mono text-primary">{children}</code>
      : <code className="block bg-muted rounded p-3 text-xs font-mono whitespace-pre-wrap overflow-x-auto">{children}</code>,
  pre: ({ children }: React.ComponentProps<"pre">) => <pre className="my-2 rounded overflow-hidden">{children}</pre>,
  table: ({ children }: React.ComponentProps<"table">) => (
    <div className="overflow-x-auto my-3">
      <table className="w-full text-xs border-collapse border border-border rounded">{children}</table>
    </div>
  ),
  thead: ({ children }: React.ComponentProps<"thead">) => <thead className="bg-muted/60">{children}</thead>,
  tr: ({ children }: React.ComponentProps<"tr">) => <tr className="border-b border-border even:bg-muted/20">{children}</tr>,
  th: ({ children }: React.ComponentProps<"th">) => <th className="px-3 py-1.5 text-left font-semibold border-r border-border last:border-r-0">{children}</th>,
  td: ({ children }: React.ComponentProps<"td">) => <td className="px-3 py-1.5 border-r border-border last:border-r-0">{children}</td>,
  hr: () => <hr className="my-4 border-border" />,
  strong: ({ children }: React.ComponentProps<"strong">) => <strong className="font-semibold">{children}</strong>,
  a: ({ href, children }: React.ComponentProps<"a">) => (
    <a href={href} className="text-primary underline underline-offset-2 hover:opacity-80" target="_blank" rel="noopener noreferrer">{children}</a>
  ),
};

export default function TasksPage() {
  const [tasks, setTasks] = useState<AiTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [fullResults, setFullResults] = useState<Record<string, string>>({});
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [followUpOpen, setFollowUpOpen] = useState<Set<string>>(new Set());
  const [followUpState, setFollowUpState] = useState<Record<string, FollowUpState>>({});
  const [promptExpanded, setPromptExpanded] = useState<Set<string>>(new Set());
  const [draggingId, setDraggingId] = useState<string | null>(null);
  const [dragOverId, setDragOverId] = useState<string | null>(null);

  type VidDetail = { id: string; title: string; url: string; channel: string; duration_sec: number; segments: { time_str: string; text: string }[]; fullText: string };
  const [vidDetail, setVidDetail] = useState<VidDetail | null>(null);
  const [vidDetailLoading, setVidDetailLoading] = useState(false);

  async function openVidDetail(vid: string, title: string) {
    setVidDetail({ id: vid, title, url: `https://www.youtube.com/watch?v=${vid}`, channel: "", duration_sec: 0, segments: [], fullText: "" });
    setVidDetailLoading(true);
    try {
      const res = await fetch(`/api/history?id=${vid}`);
      const data = await res.json();
      setVidDetail({
        id: vid,
        title: data.title || title,
        url: data.url || `https://www.youtube.com/watch?v=${vid}`,
        channel: data.channel || "",
        duration_sec: data.duration_sec || 0,
        segments: data.segments || [],
        fullText: data.fullText || "",
      });
    } finally {
      setVidDetailLoading(false);
    }
  }

  const loadTasks = useCallback(async () => {
    const res = await fetch("/api/tasks");
    const data = await res.json();
    setTasks(Array.isArray(data) ? data : []);
    setLoading(false);
  }, []);

  useEffect(() => { loadTasks(); }, [loadTasks]);

  useEffect(() => {
    const hasRunning = tasks.some(t => t.status === "running" || t.status === "pending");
    if (!hasRunning) return;
    const timer = setInterval(loadTasks, 3000);
    return () => clearInterval(timer);
  }, [tasks, loadTasks]);

  async function expandTask(taskId: string) {
    if (!expanded.has(taskId) && !fullResults[taskId]) {
      const res = await fetch(`/api/tasks/${taskId}`);
      const data = await res.json();
      if (data.result_text) setFullResults(prev => ({ ...prev, [taskId]: data.result_text }));
    }
    setExpanded(prev => {
      const next = new Set(prev);
      if (next.has(taskId)) next.delete(taskId); else next.add(taskId);
      return next;
    });
  }

  async function copyResult(taskId: string) {
    let text = fullResults[taskId];
    if (!text) {
      const res = await fetch(`/api/tasks/${taskId}`);
      const data = await res.json();
      text = data.result_text || "";
      if (text) setFullResults(prev => ({ ...prev, [taskId]: text }));
    }
    await navigator.clipboard.writeText(text);
    setCopiedId(taskId);
    setTimeout(() => setCopiedId(null), 2000);
  }

  function toggleFollowUp(taskId: string) {
    setFollowUpOpen(prev => {
      const next = new Set(prev);
      if (next.has(taskId)) next.delete(taskId); else next.add(taskId);
      return next;
    });
    if (!followUpState[taskId]) {
      setFollowUpState(prev => ({ ...prev, [taskId]: { prompt: "", model: "sonnet", submitting: false } }));
    }
  }

  async function submitFollowUp(task: AiTask) {
    const state = followUpState[task.id];
    if (!state?.prompt.trim()) return;

    setFollowUpState(prev => ({ ...prev, [task.id]: { ...prev[task.id], submitting: true } }));

    await fetch("/api/tasks", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        video_ids: task.video_ids,
        prompt: state.prompt,
        output_type: task.output_type,
        model: state.model,
        parent_task_id: task.id,
      }),
    });

    // Reset form and close
    setFollowUpState(prev => ({ ...prev, [task.id]: { prompt: "", model: state.model, submitting: false } }));
    setFollowUpOpen(prev => { const next = new Set(prev); next.delete(task.id); return next; });
    await loadTasks();
  }

  async function reparentTask(taskId: string, newParentId: string | null) {
    await fetch(`/api/tasks/${taskId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ parent_task_id: newParentId }),
    });
    await loadTasks();
  }

  function getDescendantIds(taskId: string, map: Record<string, AiTask[]>): Set<string> {
    const ids = new Set<string>();
    const queue = [taskId];
    while (queue.length) {
      const cur = queue.shift()!;
      (map[cur] || []).forEach(c => { ids.add(c.id); queue.push(c.id); });
    }
    return ids;
  }

  // Build tree: root tasks + children map (sorted by created_at)
  const taskIds = new Set(tasks.map(t => t.id));
  const rootTasks = tasks.filter(t => !t.parent_task_id || !taskIds.has(t.parent_task_id));
  const childrenMap: Record<string, AiTask[]> = {};
  tasks.filter(t => t.parent_task_id && taskIds.has(t.parent_task_id)).forEach(t => {
    const pid = t.parent_task_id!;
    if (!childrenMap[pid]) childrenMap[pid] = [];
    childrenMap[pid].push(t);
  });
  Object.values(childrenMap).forEach(arr => arr.sort((a, b) => a.created_at.localeCompare(b.created_at)));

  const renderCard = (task: AiTask, isChild: boolean) => {
    const isDragging = draggingId === task.id;
    const isDropTarget = dragOverId === task.id && draggingId !== task.id;

    function handleDragStart(e: React.DragEvent) {
      e.stopPropagation();
      e.dataTransfer.effectAllowed = "move";
      e.dataTransfer.setData("text/plain", task.id);
      setDraggingId(task.id);
    }
    function handleDragEnd() {
      setDraggingId(null);
      setDragOverId(null);
    }
    function handleDragOver(e: React.DragEvent) {
      const draggedId = e.dataTransfer.types.includes("text/plain") ? draggingId : null;
      if (!draggedId || draggedId === task.id) return;
      const descendants = getDescendantIds(draggedId, childrenMap);
      if (descendants.has(task.id)) return;
      e.preventDefault();
      e.dataTransfer.dropEffect = "move";
      setDragOverId(task.id);
    }
    function handleDragLeave(e: React.DragEvent) {
      if (!(e.currentTarget as HTMLElement).contains(e.relatedTarget as Node)) {
        setDragOverId(null);
      }
    }
    async function handleDrop(e: React.DragEvent) {
      e.preventDefault();
      setDragOverId(null);
      const draggedId = e.dataTransfer.getData("text/plain");
      if (!draggedId || draggedId === task.id) return;
      const descendants = getDescendantIds(draggedId, childrenMap);
      if (descendants.has(task.id)) return;
      setDraggingId(null);
      await reparentTask(draggedId, task.id);
    }

    return (
    <div key={task.id}>
      {isChild && (
        <div className="flex items-center justify-between gap-1 text-[10px] text-muted-foreground mb-1 pl-1 mt-2 pr-1">
          <div className="flex items-center gap-1">
            <CornerDownRight className="w-3 h-3" />
            <span>후속 질문</span>
          </div>
          <button
            className="opacity-40 hover:opacity-100 transition-opacity"
            title="부모에서 분리"
            onClick={() => reparentTask(task.id, null)}
          >
            <X className="w-3 h-3" />
          </button>
        </div>
      )}
      <Card
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={[
          isChild ? "border-primary/20 bg-primary/[0.02]" : "",
          isDragging ? "opacity-40 scale-[0.99]" : "",
          isDropTarget ? "ring-2 ring-primary border-primary bg-primary/5" : "",
          "transition-all",
        ].filter(Boolean).join(" ")}
      >
        <CardHeader className="pb-3">
          <div className="flex items-start justify-between gap-4">
            <div
              draggable
              onDragStart={handleDragStart}
              onDragEnd={handleDragEnd}
              className="cursor-grab active:cursor-grabbing pt-0.5 shrink-0 text-muted-foreground/40 hover:text-muted-foreground transition-colors select-none"
              title="드래그하여 이동"
            >
              <GripVertical className="w-4 h-4" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap mb-1.5">
                {task.status === "done" && <Badge variant="outline" className="text-green-600 border-green-300 text-[10px]">완료</Badge>}
                {(task.status === "running" || task.status === "pending") && <Badge variant="secondary" className="animate-pulse text-[10px]">처리중</Badge>}
                {task.status === "error" && <Badge variant="destructive" className="text-[10px]">오류</Badge>}
                <Badge variant="outline" className="text-[10px]">{OUTPUT_TYPE_LABEL[task.output_type] || task.output_type}</Badge>
                <Badge variant="secondary" className="text-[10px] font-mono">{task.model}</Badge>
                <span className="text-[11px] text-muted-foreground flex items-center gap-1">
                  <Clock className="w-3 h-3" />{fmtTime(task.created_at)}
                </span>
              </div>
              <p
                className={`text-sm font-medium mb-1 cursor-pointer ${promptExpanded.has(task.id) ? "" : "line-clamp-2"}`}
                onClick={() => setPromptExpanded(prev => {
                  const next = new Set(prev);
                  if (next.has(task.id)) next.delete(task.id); else next.add(task.id);
                  return next;
                })}
                title={promptExpanded.has(task.id) ? "클릭하여 접기" : "클릭하여 전체 보기"}
              >{task.prompt}</p>
              {!isChild && task.video_ids.length > 0 && (
                <div className="flex gap-1.5 mt-1.5 overflow-x-auto pb-0.5 scrollbar-none">
                  {task.video_ids.slice(0, 5).map(vid => (
                    <button
                      key={vid}
                      type="button"
                      title={`${task.video_titles[vid] || vid} — 클릭하여 상세 보기`}
                      className="flex items-center gap-1.5 shrink-0 bg-muted/50 hover:bg-muted rounded-md pl-0 pr-2 py-0 min-w-0 max-w-[160px] overflow-hidden transition-colors text-left"
                      onClick={e => { e.stopPropagation(); openVidDetail(vid, task.video_titles[vid] || vid); }}
                    >
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img
                        src={`https://img.youtube.com/vi/${vid}/mqdefault.jpg`}
                        alt={task.video_titles[vid] || vid}
                        className="w-10 aspect-video object-cover rounded-l-md shrink-0"
                        loading="lazy"
                      />
                      <span className="text-[10px] text-muted-foreground truncate leading-tight">
                        {task.video_titles[vid] || vid}
                      </span>
                    </button>
                  ))}
                  {task.video_ids.length > 5 && (
                    <span className="text-[10px] text-muted-foreground self-center shrink-0">
                      +{task.video_ids.length - 5}개
                    </span>
                  )}
                </div>
              )}
            </div>
            {(task.status === "running" || task.status === "pending") && (
              <Loader2 className="w-4 h-4 animate-spin text-muted-foreground shrink-0 mt-1" />
            )}
            {task.status === "error" && (
              <AlertCircle className="w-4 h-4 text-destructive shrink-0 mt-1" />
            )}
          </div>
        </CardHeader>

        {task.status === "done" && (
          <CardContent className="space-y-3 pt-0">
            <div className="relative">
              <div className={`bg-muted/20 rounded-lg px-4 py-3 ${
                expanded.has(task.id) ? "max-h-[70vh] overflow-y-auto" : "max-h-40 overflow-hidden"
              }`}>
                {task.output_type === "markdown" ? (
                  <ReactMarkdown remarkPlugins={[remarkGfm]} components={mdComponents}>
                    {expanded.has(task.id) && fullResults[task.id]
                      ? fullResults[task.id]
                      : (task.result_preview || "결과 없음")}
                  </ReactMarkdown>
                ) : (
                  <pre className="text-xs leading-relaxed whitespace-pre-wrap font-mono">
                    {expanded.has(task.id) && fullResults[task.id]
                      ? fullResults[task.id]
                      : (task.result_preview || "결과 없음")}
                  </pre>
                )}
              </div>
              {!expanded.has(task.id) && (task.result_preview?.length || 0) >= 200 && (
                <div className="absolute bottom-0 left-0 right-0 h-10 bg-gradient-to-t from-background to-transparent pointer-events-none rounded-b-lg" />
              )}
            </div>
            <div className="flex gap-2 flex-wrap">
              <Button variant="ghost" size="sm" className="text-xs h-7" onClick={() => expandTask(task.id)}>
                <FileText className="w-3.5 h-3.5 mr-1" />
                {expanded.has(task.id) ? "접기" : "전체 결과 보기"}
              </Button>
              <Button variant="ghost" size="sm" className="text-xs h-7" onClick={() => copyResult(task.id)}>
                {copiedId === task.id
                  ? <><Check className="w-3.5 h-3.5 mr-1 text-green-600" />복사됨</>
                  : <><Copy className="w-3.5 h-3.5 mr-1" />복사</>}
              </Button>
              {task.output_type !== "text" && (
                <a href={`/api/tasks/${task.id}/download`} download>
                  <Button variant="outline" size="sm" className="text-xs h-7">
                    <Download className="w-3.5 h-3.5 mr-1" />
                    다운로드 ({OUTPUT_TYPE_LABEL[task.output_type] || task.output_type})
                  </Button>
                </a>
              )}
              <Button
                variant={followUpOpen.has(task.id) ? "secondary" : "ghost"}
                size="sm"
                className="text-xs h-7 ml-auto"
                onClick={() => toggleFollowUp(task.id)}
              >
                <MessageSquarePlus className="w-3.5 h-3.5 mr-1" />
                계속 질문하기
              </Button>
            </div>
            {followUpOpen.has(task.id) && (
              <div className="border border-primary/20 rounded-lg p-3 bg-primary/5 space-y-2">
                <p className="text-[11px] text-muted-foreground font-medium">이전 분석 결과를 바탕으로 추가 질문</p>
                <textarea
                  className="w-full text-sm rounded-md border border-input bg-background px-3 py-2 placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring resize-none"
                  rows={3}
                  placeholder="추가로 분석하거나 물어볼 내용을 입력하세요..."
                  value={followUpState[task.id]?.prompt || ""}
                  onChange={e => setFollowUpState(prev => ({
                    ...prev,
                    [task.id]: { ...prev[task.id], prompt: e.target.value }
                  }))}
                  onKeyDown={e => {
                    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) submitFollowUp(task);
                  }}
                />
                <div className="flex items-center gap-2">
                  <select
                    className="text-xs border border-input rounded-md px-2 py-1 bg-background focus:outline-none focus:ring-1 focus:ring-ring"
                    value={followUpState[task.id]?.model || "sonnet"}
                    onChange={e => setFollowUpState(prev => ({
                      ...prev,
                      [task.id]: { ...prev[task.id], model: e.target.value }
                    }))}
                  >
                    {MODEL_OPTIONS.map(o => (
                      <option key={o.value} value={o.value}>{o.label}</option>
                    ))}
                  </select>
                  <span className="text-[10px] text-muted-foreground">⌘+Enter로 전송</span>
                  <Button
                    size="sm"
                    className="text-xs h-7 ml-auto"
                    disabled={!followUpState[task.id]?.prompt.trim() || followUpState[task.id]?.submitting}
                    onClick={() => submitFollowUp(task)}
                  >
                    {followUpState[task.id]?.submitting
                      ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      : <><Send className="w-3.5 h-3.5 mr-1" />전송</>}
                  </Button>
                </div>
              </div>
            )}
          </CardContent>
        )}

        {task.status === "error" && task.error_msg && (
          <CardContent className="pt-0 space-y-2">
            <p className="text-xs text-destructive">{task.error_msg}</p>
          </CardContent>
        )}
      </Card>
    </div>
    );
  };

  function renderTree(task: AiTask, depth: number): React.ReactNode {
    const children = childrenMap[task.id] || [];
    return (
      <div key={task.id}>
        {renderCard(task, depth > 0)}
        {children.length > 0 && (
          <div className="pl-6 border-l-2 border-primary/15 ml-3">
            {children.map(child => renderTree(child, depth + 1))}
          </div>
        )}
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20 text-muted-foreground">
        <Loader2 className="w-5 h-5 animate-spin mr-2" />로딩 중...
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold tracking-tight">AI 작업 이력</h2>
        <Button variant="outline" size="sm" onClick={loadTasks}>
          <RefreshCw className="w-3.5 h-3.5 mr-1.5" />새로고침
        </Button>
      </div>

      {tasks.length === 0 && (
        <div className="text-center py-16 text-muted-foreground">
          <Briefcase className="w-10 h-10 mx-auto mb-3 opacity-30" />
          <p className="text-sm">AI 작업 이력이 없습니다.</p>
          <p className="text-xs mt-1">대시보드에서 영상을 선택하고 AI 작업을 의뢰해보세요.</p>
        </div>
      )}

      {rootTasks.map(task => renderTree(task, 0))}

      {/* 영상 상세 모달 */}
      {vidDetail && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
          onClick={() => setVidDetail(null)}
        >
          <div
            className="bg-background rounded-xl shadow-2xl w-full max-w-lg mx-4 max-h-[80vh] flex flex-col"
            onClick={e => e.stopPropagation()}
          >
            {/* 헤더 */}
            <div className="flex items-start justify-between gap-3 p-4 border-b">
              <div className="min-w-0">
                <p className="font-semibold text-sm leading-snug line-clamp-2">{vidDetail.title}</p>
                {vidDetail.channel && (
                  <p className="text-xs text-muted-foreground mt-0.5">{vidDetail.channel}</p>
                )}
              </div>
              <div className="flex items-center gap-1 shrink-0">
                <a href={vidDetail.url} target="_blank" rel="noopener noreferrer">
                  <Button variant="ghost" size="icon" className="h-7 w-7">
                    <ExternalLink className="w-3.5 h-3.5" />
                  </Button>
                </a>
                <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => setVidDetail(null)}>
                  <X className="w-4 h-4" />
                </Button>
              </div>
            </div>
            {/* 썸네일 */}
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={`https://img.youtube.com/vi/${vidDetail.id}/mqdefault.jpg`}
              alt={vidDetail.title}
              className="w-full aspect-video object-cover"
            />
            {/* 트랜스크립트 */}
            <div className="flex-1 overflow-y-auto p-3">
              {vidDetailLoading ? (
                <div className="flex items-center justify-center py-8 text-muted-foreground">
                  <Loader2 className="w-4 h-4 animate-spin mr-2" />로딩 중...
                </div>
              ) : vidDetail.segments.length > 0 ? (
                <div className="space-y-0.5">
                  {vidDetail.segments.map((seg, i) => (
                    <div key={i} className="flex gap-2 py-1 hover:bg-muted/50 rounded px-1.5">
                      <span className="text-[10px] font-mono text-primary font-semibold shrink-0 pt-0.5 w-14">{seg.time_str}</span>
                      <span className="text-[11px] leading-relaxed">{seg.text}</span>
                    </div>
                  ))}
                </div>
              ) : vidDetail.fullText ? (
                <pre className="text-xs leading-relaxed whitespace-pre-wrap font-mono">{vidDetail.fullText}</pre>
              ) : (
                <p className="text-xs text-muted-foreground text-center py-6">트랜스크립트 없음</p>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
