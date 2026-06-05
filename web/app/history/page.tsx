"use client";
export const dynamic = 'force-dynamic';
import { useState, useEffect, useCallback, useRef } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Video, Layers, Clock, FileText, ExternalLink, Copy, X, Search, Image as ImageIcon,
  Loader2, Plus, MessageSquare, Send, CheckSquare, Square, Bot, Share2, Check, Briefcase, Mic,
} from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { API_BASE } from "@/lib/types";
import { useTaskProgress } from "@/lib/useTaskProgress";
import { SttLayer } from "@/components/SttLayer";
import PlaylistModal from "@/components/PlaylistModal";

interface HistoryItem {
  id: string; title: string; channel: string; url: string;
  duration_sec: number; text_length: number; segments: number;
  language: string; processed_at: string; preview: string;
  thumbnail?: string;
  stt_status?: "pending";
  slide_count?: number;
}
interface Summary {
  total: number;
  channels: Record<string, { count: number; totalDuration: number; totalChars: number }>;
  totalDuration: number; totalChars: number;
}

function fmtDur(sec: number) {
  const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60);
  return h > 0 ? `${h}시간 ${m}분` : `${m}분`;
}

export default function HistoryPage() {
  const [items, setItems] = useState<HistoryItem[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [filter, setFilter] = useState("all");
  const [selected, setSelected] = useState<HistoryItem | null>(null);
  const [fullText, setFullText] = useState("");
  const [segments, setSegments] = useState<any[]>([]);
  const [slides, setSlides] = useState<Array<{slide_index: number; filename: string; time_str: string; ocr_text: string}>>([]);
  const [textView, setTextView] = useState<"full" | "timeline">("timeline");
  const [search, setSearch] = useState("");
  const [collections, setCollections] = useState<any[]>([]);
  const [activeCollection, setActiveCollection] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<"grid" | "list">("grid");
  const sttPendingTask = useTaskProgress();
  const [sttLayerOpen, setSttLayerOpen] = useState(false);
  const [playlistModalOpen, setPlaylistModalOpen] = useState(false);

  // 플레이리스트 (채널 하위 묶음)
  const [playlists, setPlaylists] = useState<any[]>([]);
  const [activePlaylist, setActivePlaylist] = useState<string | null>(null);
  const [playlistVideoIds, setPlaylistVideoIds] = useState<Set<string> | null>(null);

  // 질문하기 chat state
  type ChatMsg = { role: "user" | "assistant"; content: string };
  const [chatHistories, setChatHistories] = useState<Record<string, ChatMsg[]>>({});
  const [chatInput, setChatInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  // 다중 선택 + 멀티 AI 질문
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [multiAskOpen, setMultiAskOpen] = useState(false);
  const [multiChatMsgs, setMultiChatMsgs] = useState<ChatMsg[]>([]);
  const [multiChatInput, setMultiChatInput] = useState("");
  const [multiChatLoading, setMultiChatLoading] = useState(false);
  const multiChatEndRef = useRef<HTMLDivElement>(null);

  const chatMsgs: ChatMsg[] = selected ? (chatHistories[selected.id] ?? []) : [];

  useEffect(() => {
    try {
      const saved = localStorage.getItem("ot_chat_histories");
      if (saved) setChatHistories(JSON.parse(saved));
    } catch {}
  }, []);

  function updateChatMsgs(videoId: string, updater: (prev: ChatMsg[]) => ChatMsg[]) {
    setChatHistories(prev => {
      const next = { ...prev, [videoId]: updater(prev[videoId] ?? []) };
      try { localStorage.setItem("ot_chat_histories", JSON.stringify(next)); } catch {}
      return next;
    });
  }

  const router = useRouter();
  const searchParams = useSearchParams();

  // ?vid=... 파라미터로 진입 시 해당 영상 자동 선택
  useEffect(() => {
    const vid = searchParams.get("vid");
    if (!vid || items.length === 0) return;
    const target = items.find(i => i.id === vid);
    if (target) selectItem(target);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [items, searchParams]);

  const [taskPanelOpen, setTaskPanelOpen] = useState(false);
  const [taskPrompt, setTaskPrompt] = useState("");
  const [taskOutputType, setTaskOutputType] = useState("markdown");
  const [taskModel, setTaskModel] = useState("sonnet");
  const [taskSubmitting, setTaskSubmitting] = useState(false);

  const TASK_PRESETS = [
    { label: "핵심 인사이트", prompt: "영상에서 핵심 인사이트 5가지를 추출하고 각각 구체적으로 설명해주세요." },
    { label: "블로그 포스트", prompt: "이 영상 내용을 바탕으로 독자가 공감할 수 있는 블로그 포스트를 작성해주세요." },
    { label: "한 페이지 요약", prompt: "영상 내용을 핵심만 담아 한 페이지 분량으로 요약해주세요." },
    { label: "강의 노트", prompt: "영상 내용을 개요, 주요 개념, 핵심 포인트 형식의 강의 노트로 정리해주세요." },
  ];

  const [shareToken, setShareToken] = useState<string | null>(null);
  const [sharing, setSharing] = useState(false);
  const [shareCopied, setShareCopied] = useState(false);

  const refreshDashboard = useCallback(() => {
    fetch("/api/history")
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(d => {
        setItems(d.items || []);
        setSummary(d.summary || null);
        setCollections(d.collections || []);
      })
      .catch(err => console.error("[history] failed to load dashboard:", err));
  }, []);

  useEffect(() => {
    refreshDashboard();
  }, [refreshDashboard]);

  // 채널 변경 시 해당 채널의 플레이리스트 로드
  useEffect(() => {
    if (filter === "all") {
      setPlaylists([]);
      setActivePlaylist(null);
      setPlaylistVideoIds(null);
      return;
    }
    fetch(`${API_BASE}/api/playlists?channel=${encodeURIComponent(filter)}`)
      .then(r => r.ok ? r.json() : [])
      .then(data => setPlaylists(data))
      .catch(() => setPlaylists([]));
    setActivePlaylist(null);
    setPlaylistVideoIds(null);
  }, [filter]);

  // 플레이리스트 선택 시 해당 영상 ID Set 로드
  useEffect(() => {
    if (!activePlaylist) { setPlaylistVideoIds(null); return; }
    fetch(`${API_BASE}/api/playlists/${activePlaylist}/videos`)
      .then(r => r.ok ? r.json() : [])
      .then((videos: any[]) => setPlaylistVideoIds(new Set(videos.map(v => v.id))))
      .catch(() => setPlaylistVideoIds(null));
  }, [activePlaylist]);

  // 영상 선택 시 채팅 초기화
  async function selectItem(item: HistoryItem) {
    setSelected(item);
    setSegments([]);
    setSlides([]);
    setChatInput("");
    const res = await fetch(`/api/history?id=${item.id}`);
    const data = await res.json();
    setFullText(data.fullText || "");
    if (data.segments) setSegments(data.segments);
    try {
      const slideRes = await fetch(`${API_BASE}/api/slides/${item.id}`);
      if (slideRes.ok) {
        const sd = await slideRes.json();
        setSlides(sd.slides || []);
      }
    } catch {}
  }

  async function sendQuestion() {
    if (!chatInput.trim() || !selected || chatLoading) return;
    const q = chatInput.trim();
    const videoId = selected.id;
    setChatInput("");
    const newMsgs: ChatMsg[] = [...chatMsgs, { role: "user", content: q }];
    updateChatMsgs(videoId, () => newMsgs);
    setChatLoading(true);

    updateChatMsgs(videoId, prev => [...prev, { role: "assistant", content: "" }]);

    try {
      const res = await fetch("/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          video_id: videoId,
          question: q,
          history: chatMsgs,
        }),
      });
      if (!res.body) throw new Error("no body");
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let full = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value);
        for (const line of chunk.split("\n")) {
          if (!line.startsWith("data: ")) continue;
          try {
            const data = JSON.parse(line.slice(6));
            if (data.text) {
              full += data.text;
              updateChatMsgs(videoId, prev => {
                const updated = [...prev];
                updated[updated.length - 1] = { role: "assistant", content: full };
                return updated;
              });
              chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
            }
          } catch {}
        }
      }
    } catch (e) {
      updateChatMsgs(videoId, prev => {
        const updated = [...prev];
        updated[updated.length - 1] = { role: "assistant", content: "오류가 발생했습니다." };
        return updated;
      });
    } finally {
      setChatLoading(false);
    }
  }

  function toggleSelect(id: string) {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function startSttForPending(item: HistoryItem) {
    try {
      const res = await fetch(`${API_BASE}/api/transcribe/youtube`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: item.url, language: "ko" }),
      });
      const data = await res.json();
      if (data.task_id) {
        sttPendingTask.start(data.task_id);
      }
    } catch {
      alert("STT 분석 시작 실패 — API 연결을 확인하세요");
    }
  }

  async function shareVideo(id: string) {
    setSharing(true);
    setShareToken(null);
    setShareCopied(false);
    try {
      const res = await fetch("/api/share", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ video_id: id }),
      });
      const data = await res.json();
      if (data.token) {
        setShareToken(data.token);
        const shareUrl = `${window.location.origin}/share/${data.token}`;
        await navigator.clipboard.writeText(shareUrl);
        setShareCopied(true);
        setTimeout(() => setShareCopied(false), 3000);
      }
    } catch {
      alert("공유 링크 생성 실패");
    } finally {
      setSharing(false);
    }
  }

  async function sendMultiQuestion() {
    if (!multiChatInput.trim() || multiChatLoading || selectedIds.size === 0) return;
    const q = multiChatInput.trim();
    setMultiChatInput("");
    const newMsgs: ChatMsg[] = [...multiChatMsgs, { role: "user", content: q }];
    setMultiChatMsgs(newMsgs);
    setMultiChatLoading(true);
    setMultiChatMsgs(prev => [...prev, { role: "assistant", content: "" }]);

    try {
      const res = await fetch("/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          video_ids: Array.from(selectedIds),
          question: q,
          history: multiChatMsgs,
        }),
      });
      if (!res.body) throw new Error("no body");
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let full = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value);
        for (const line of chunk.split("\n")) {
          if (!line.startsWith("data: ")) continue;
          try {
            const data = JSON.parse(line.slice(6));
            if (data.text) {
              full += data.text;
              setMultiChatMsgs(prev => {
                const updated = [...prev];
                updated[updated.length - 1] = { role: "assistant", content: full };
                return updated;
              });
              multiChatEndRef.current?.scrollIntoView({ behavior: "smooth" });
            }
          } catch {}
        }
      }
    } catch {
      setMultiChatMsgs(prev => {
        const updated = [...prev];
        updated[updated.length - 1] = { role: "assistant", content: "오류가 발생했습니다." };
        return updated;
      });
    } finally {
      setMultiChatLoading(false);
    }
  }

  async function submitTask() {
    if (!taskPrompt.trim() || taskSubmitting) return;
    setTaskSubmitting(true);
    try {
      const res = await fetch("/api/tasks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          video_ids: Array.from(selectedIds),
          prompt: taskPrompt,
          output_type: taskOutputType,
          model: taskModel,
        }),
      });
      const data = await res.json();
      if (data.ai_task_id) {
        setTaskPanelOpen(false);
        setTaskPrompt("");
        setSelectedIds(new Set());
        router.push("/tasks");
      }
    } catch {
      alert("작업 생성 실패");
    } finally {
      setTaskSubmitting(false);
    }
  }

  const filtered = items.filter(i => {
    if (activeCollection && (i as any).collection_id !== activeCollection) return false;
    if (!activeCollection && filter !== "all" && i.channel !== filter) return false;
    if (playlistVideoIds && !playlistVideoIds.has(i.id)) return false;
    if (search && !i.title.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  const statCards = summary ? [
    { label: "총 영상", value: summary.total, icon: Video, color: "text-blue-600" },
    { label: "채널", value: Object.keys(summary.channels).length, icon: Layers, color: "text-violet-600" },
    { label: "총 시간", value: fmtDur(summary.totalDuration), icon: Clock, color: "text-emerald-600" },
    { label: "총 글자수", value: `${(summary.totalChars / 1000).toFixed(0)}K`, icon: FileText, color: "text-amber-600" },
  ] : [];

  return (
    <div className="space-y-6">
      {/* STT Layer */}
      <SttLayer open={sttLayerOpen} onClose={() => setSttLayerOpen(false)} onTaskDone={refreshDashboard} />
      <PlaylistModal isOpen={playlistModalOpen} channel={filter !== "all" ? filter : ""} onClose={() => setPlaylistModalOpen(false)} />

      {/* 헤더 + 버튼 */}
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold tracking-tight">대시보드</h2>
        <div className="flex items-center gap-2">
          {selectedIds.size >= 1 && (
            <Button
              size="sm"
              variant="outline"
              onClick={() => { setTaskPanelOpen(!taskPanelOpen); setMultiAskOpen(false); }}
            >
              <Briefcase className="w-4 h-4 mr-1.5" />
              AI 작업 의뢰
            </Button>
          )}
          {selectedIds.size >= 2 && (
            <Button
              size="sm"
              variant="secondary"
              onClick={() => { setMultiAskOpen(true); setMultiChatMsgs([]); setTaskPanelOpen(false); }}
            >
              <Bot className="w-4 h-4 mr-1.5" />
              {selectedIds.size}개 영상 AI 질문
            </Button>
          )}
          {selectedIds.size > 0 && (
            <Button size="sm" variant="ghost" onClick={() => setSelectedIds(new Set())}>
              <X className="w-3.5 h-3.5 mr-1" />선택 해제
            </Button>
          )}
          <Button onClick={() => setSttLayerOpen(true)} size="sm">
            <Plus className="w-4 h-4 mr-1.5" />새 변환
          </Button>
        </div>
      </div>

      {/* 요약 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {statCards.map(s => (
          <Card key={s.label}>
            <CardContent className="pt-6 flex items-center gap-4">
              <div className={`p-2.5 rounded-xl bg-muted ${s.color}`}><s.icon className="w-5 h-5" /></div>
              <div>
                <p className="text-2xl font-bold tracking-tight">{s.value}</p>
                <p className="text-xs text-muted-foreground">{s.label}</p>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Collections */}
      {collections.length > 0 && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium">수집 작업</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {collections.map((col: any) => (
                <div
                  key={col.id}
                  onClick={() => setActiveCollection(activeCollection === col.id ? null : col.id)}
                  className={`border rounded-lg p-4 cursor-pointer transition-all hover:shadow-md ${
                    activeCollection === col.id ? "ring-2 ring-primary border-primary bg-primary/5" : ""
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <Badge variant={col.type === "single" ? "outline" : "secondary"} className="text-[10px]">
                          {col.type === "single" ? "단건" : col.type === "channel" ? "채널" : "재생목록"}
                        </Badge>
                        <Badge variant={col.status === "done" ? "outline" : "secondary"} className="text-[10px]">
                          {col.status === "done" ? "완료" : "처리중"}
                        </Badge>
                      </div>
                      <h4 className="font-medium text-sm mt-2">{col.name}</h4>
                      <p className="text-xs text-muted-foreground mt-1">
                        {col.item_count}개 영상 | {fmtDur(col.total_duration)} | {(col.total_chars / 1000).toFixed(0)}K자
                      </p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
            {activeCollection && (
              <Button variant="ghost" size="sm" className="mt-3" onClick={() => setActiveCollection(null)}>
                필터 해제
              </Button>
            )}
          </CardContent>
        </Card>
      )}

      {/* 채널 필터 */}
      {summary?.channels && !activeCollection && (
        <Card>
          <CardContent className="pt-6">
            <div className="flex gap-3 flex-wrap items-center">
              <span className="text-sm font-medium text-muted-foreground mr-1">채널:</span>
              <Button variant={filter === "all" ? "default" : "outline"} size="sm" onClick={() => setFilter("all")}>전체</Button>
              {Object.entries(summary.channels).filter(([ch]) => ch && ch !== "null").map(([ch, info]) => (
                <Button key={ch} variant={filter === ch ? "default" : "outline"} size="sm" onClick={() => setFilter(filter === ch ? "all" : ch)}>
                  {ch}<Badge variant="secondary" className="ml-2 text-[10px]">{info.count}</Badge>
                </Button>
              ))}
              <div className="ml-auto flex gap-1">
                <Button variant={viewMode === "grid" ? "secondary" : "ghost"} size="icon" className="h-8 w-8" onClick={() => setViewMode("grid")}>
                  <ImageIcon className="w-3.5 h-3.5" />
                </Button>
                <Button variant={viewMode === "list" ? "secondary" : "ghost"} size="icon" className="h-8 w-8" onClick={() => setViewMode("list")}>
                  <FileText className="w-3.5 h-3.5" />
                </Button>
              </div>
            </div>

            {/* 플레이리스트 인라인 필터 — 채널 선택 시 표시 */}
            {filter !== "all" && playlists.length > 0 && (
              <div className="mt-3 pt-3 border-t flex gap-2 flex-wrap items-center">
                <span className="text-xs text-muted-foreground font-medium shrink-0">묶음:</span>
                <button
                  onClick={() => { setActivePlaylist(null); setPlaylistVideoIds(null); }}
                  className={`text-xs px-2.5 py-1 rounded-full border transition-colors ${!activePlaylist ? "bg-primary text-primary-foreground border-primary" : "border-border hover:bg-muted"}`}
                >
                  전체
                </button>
                {playlists.map((pl: any) => (
                  <button
                    key={pl.id}
                    onClick={() => setActivePlaylist(activePlaylist === pl.id ? null : pl.id)}
                    className={`text-xs px-2.5 py-1 rounded-full border transition-colors flex items-center gap-1.5 ${activePlaylist === pl.id ? "bg-primary text-primary-foreground border-primary" : "border-border hover:bg-muted"}`}
                  >
                    {pl.title}
                    {pl.item_count > 0 && (
                      <span className={`text-[10px] px-1 rounded-full ${activePlaylist === pl.id ? "bg-primary-foreground/20" : "bg-muted"}`}>
                        {pl.item_count}
                      </span>
                    )}
                  </button>
                ))}
                <button
                  onClick={() => setPlaylistModalOpen(true)}
                  className="text-xs px-2.5 py-1 rounded-full border border-dashed border-border hover:bg-muted text-muted-foreground transition-colors"
                >
                  + 편집
                </button>
                {activePlaylist && playlistVideoIds && playlistVideoIds.size > 0 && (
                  <button
                    onClick={() => {
                      setSelectedIds(new Set(Array.from(playlistVideoIds)));
                      setMultiChatMsgs([]);
                      setMultiAskOpen(true);
                    }}
                    className="ml-auto text-xs px-3 py-1 rounded-full bg-primary text-primary-foreground hover:bg-primary/90 transition-colors flex items-center gap-1.5 shrink-0"
                  >
                    <Bot className="w-3 h-3" />
                    묶음 AI 질문
                  </button>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* 검색 */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
        <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="제목으로 검색..." className="pl-10" />
      </div>

      <p className="text-sm text-muted-foreground">{filtered.length}개 결과</p>

      <div className="flex gap-6">
        {/* 목록 */}
        <div className="flex-1 min-w-0">
          {viewMode === "grid" ? (
            /* 그리드 뷰 (썸네일) */
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {filtered.map((item) => (
                <Card
                  key={item.id}
                  className={`cursor-pointer transition-all hover:shadow-lg overflow-hidden relative ${
                    selected?.id === item.id ? "ring-2 ring-primary" : ""
                  } ${selectedIds.has(item.id) ? "ring-2 ring-blue-500" : ""}`}
                  onClick={() => selectItem(item)}
                >
                  {/* 체크박스 */}
                  <div
                    className="absolute top-2 left-2 z-10"
                    onClick={(e) => { e.stopPropagation(); toggleSelect(item.id); }}
                  >
                    {selectedIds.has(item.id)
                      ? <CheckSquare className="w-5 h-5 text-blue-500 bg-white rounded" />
                      : <Square className="w-5 h-5 text-white/70 hover:text-white drop-shadow" />}
                  </div>
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={item.thumbnail || `https://img.youtube.com/vi/${item.id}/mqdefault.jpg`}
                    alt={item.title}
                    className="w-full aspect-video object-cover"
                    loading="lazy"
                  />
                  <CardContent className="p-3 space-y-1.5">
                    <h4 className="font-medium text-xs line-clamp-2 leading-snug">{item.title}</h4>
                    <div className="flex items-center gap-2 flex-wrap">
                      {item.stt_status === "pending"
                        ? <Badge variant="outline" className="text-[9px] px-1.5 text-amber-600 border-amber-400">STT 미처리</Badge>
                        : item.channel && item.channel !== "null" && <Badge variant="outline" className="text-[9px] px-1.5">{item.channel}</Badge>
                      }
                      {item.stt_status === "pending"
                        ? <span className="text-[10px] text-muted-foreground">슬라이드 {item.slide_count}장</span>
                        : <>
                            <span className="text-[10px] text-muted-foreground">{fmtDur(item.duration_sec)}</span>
                            <span className="text-[10px] text-muted-foreground">{(item.text_length / 1000).toFixed(1)}K자</span>
                          </>
                      }
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          ) : (
            /* 리스트 뷰 */
            <div className="space-y-2">
              {filtered.map((item) => (
                <Card
                  key={item.id}
                  className={`cursor-pointer transition-all hover:shadow-md ${
                    selected?.id === item.id ? "ring-2 ring-primary shadow-md" : ""
                  } ${selectedIds.has(item.id) ? "ring-2 ring-blue-500" : ""}`}
                  onClick={() => selectItem(item)}
                >
                  <CardContent className="py-3 flex gap-3 items-center">
                    <div
                      className="shrink-0"
                      onClick={(e) => { e.stopPropagation(); toggleSelect(item.id); }}
                    >
                      {selectedIds.has(item.id)
                        ? <CheckSquare className="w-4.5 h-4.5 text-blue-500" />
                        : <Square className="w-4.5 h-4.5 text-muted-foreground hover:text-foreground" />}
                    </div>
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={item.thumbnail || `https://img.youtube.com/vi/${item.id}/mqdefault.jpg`}
                      alt={item.title}
                      className="w-28 aspect-video object-cover rounded-md shrink-0"
                      loading="lazy"
                    />
                    <div className="min-w-0 flex-1">
                      <h4 className="font-medium text-sm truncate">{item.title}</h4>
                      <div className="flex items-center gap-2 mt-1.5">
                        {item.stt_status === "pending"
                          ? <Badge variant="outline" className="text-[10px] text-amber-600 border-amber-400">STT 미처리</Badge>
                          : item.channel && item.channel !== "null" && <Badge variant="outline" className="text-[10px]">{item.channel}</Badge>
                        }
                        {item.stt_status === "pending"
                          ? <span className="text-xs text-muted-foreground">슬라이드 {item.slide_count}장</span>
                          : <>
                              <span className="text-xs text-muted-foreground">{fmtDur(item.duration_sec)}</span>
                              <span className="text-xs text-muted-foreground">{item.text_length.toLocaleString()}자</span>
                            </>
                        }
                      </div>
                    </div>
                    <a href={item.url} target="_blank" rel="noopener noreferrer" onClick={(e) => e.stopPropagation()}>
                      <Button variant="ghost" size="icon" className="h-8 w-8 shrink-0"><ExternalLink className="w-3.5 h-3.5" /></Button>
                    </a>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </div>

        {/* 상세 패널 */}
        {selected && (
          <div className="w-[420px] shrink-0">
            <Card className="sticky top-6">
              <CardHeader className="pb-3">
                <div className="flex justify-between items-start">
                  <CardTitle className="text-sm leading-snug pr-4">{selected.title}</CardTitle>
                  <Button variant="ghost" size="icon" className="h-7 w-7 shrink-0" onClick={() => setSelected(null)}>
                    <X className="w-4 h-4" />
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* 썸네일 */}
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={selected.thumbnail || `https://img.youtube.com/vi/${selected.id}/mqdefault.jpg`}
                  alt={selected.title}
                  className="w-full aspect-video object-cover rounded-lg"
                />

                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div className="text-muted-foreground">채널</div><div className="font-medium">{selected.channel && selected.channel !== "null" ? selected.channel : "-"}</div>
                  <div className="text-muted-foreground">길이</div><div className="font-medium">{fmtDur(selected.duration_sec)}</div>
                  <div className="text-muted-foreground">텍스트</div><div className="font-medium">{selected.text_length.toLocaleString()}자</div>
                  <div className="text-muted-foreground">세그먼트</div><div className="font-medium">{selected.segments}</div>
                </div>

                <div className="flex gap-2 flex-wrap">
                  <a href={selected.url} target="_blank" rel="noopener noreferrer">
                    <Button variant="outline" size="sm">
                      <ExternalLink className="w-3.5 h-3.5 mr-1.5" />YouTube
                    </Button>
                  </a>
                  <Button variant="outline" size="sm" onClick={() => navigator.clipboard.writeText(fullText)}>
                    <Copy className="w-3.5 h-3.5 mr-1.5" />복사
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => shareVideo(selected.id)}
                    disabled={sharing}
                  >
                    {sharing ? (
                      <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                    ) : shareCopied ? (
                      <Check className="w-3.5 h-3.5 mr-1.5 text-green-600" />
                    ) : (
                      <Share2 className="w-3.5 h-3.5 mr-1.5" />
                    )}
                    {shareCopied ? "링크 복사됨!" : "공유"}
                  </Button>
                </div>

                <Separator />

                {/* STT 미처리 영상: 분석 시작 CTA */}
                {selected.stt_status === "pending" && (
                  <div className="rounded-lg border border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-900/20 p-4 space-y-3">
                    <div className="flex items-center gap-2">
                      <Loader2 className={`w-4 h-4 text-amber-600 ${sttPendingTask.status === "running" ? "animate-spin" : "hidden"}`} />
                      <p className="text-sm font-medium text-amber-800 dark:text-amber-300">STT 분석이 필요합니다</p>
                    </div>
                    <p className="text-xs text-amber-700 dark:text-amber-400">YouTube 자막 우선 다운로드, 없으면 Whisper로 오디오 변환합니다.</p>
                    {sttPendingTask.status === "running" && (
                      <p className="text-xs text-amber-600">{sttPendingTask.message}</p>
                    )}
                    {sttPendingTask.status === "done" && (
                      <div className="flex items-center gap-2">
                        <Check className="w-4 h-4 text-green-600" />
                        <p className="text-xs text-green-700">분석 완료! 새로고침하면 대시보드에 반영됩니다.</p>
                        <Button size="sm" variant="outline" className="h-6 text-[11px]" onClick={refreshDashboard}>새로고침</Button>
                      </div>
                    )}
                    {sttPendingTask.status !== "running" && sttPendingTask.status !== "done" && (
                      <Button size="sm" onClick={() => startSttForPending(selected)} className="bg-amber-600 hover:bg-amber-700 text-white">
                        <Mic className="w-3.5 h-3.5 mr-1.5" />STT 분석 시작
                      </Button>
                    )}
                  </div>
                )}

                <Tabs defaultValue={selected.stt_status === "pending" ? "slides" : "text"}>
                  <TabsList className="w-full">
                    <TabsTrigger value="text" className="flex-1">텍스트</TabsTrigger>
                    <TabsTrigger value="ask" className="flex-1">
                      <MessageSquare className="w-3 h-3 mr-1" />질문하기
                    </TabsTrigger>
                    <TabsTrigger value="slides" className="flex-1">
                      <ImageIcon className="w-3 h-3 mr-1" />슬라이드{slides.length > 0 && <Badge variant="secondary" className="ml-1 text-[9px]">{slides.length}</Badge>}
                    </TabsTrigger>
                  </TabsList>
                  <TabsContent value="text">
                    <div className="flex gap-1.5 mb-2">
                      <Button variant={textView === "timeline" ? "secondary" : "ghost"} size="sm" className="h-7 text-[11px]" onClick={() => setTextView("timeline")}>
                        <Clock className="w-3 h-3 mr-1" />타임라인
                      </Button>
                      <Button variant={textView === "full" ? "secondary" : "ghost"} size="sm" className="h-7 text-[11px]" onClick={() => setTextView("full")}>
                        <FileText className="w-3 h-3 mr-1" />전체 텍스트
                      </Button>
                    </div>
                    {textView === "timeline" ? (
                      segments.length > 0 ? (
                        <div className="h-[280px] overflow-y-auto space-y-0.5 border rounded-lg p-2">
                          {segments.map((seg: any, i: number) => (
                            <div key={i} className="flex gap-2 py-1 hover:bg-muted/50 rounded px-1.5 group">
                              <span className="text-[10px] font-mono text-primary font-semibold shrink-0 pt-0.5 w-14">{seg.time_str}</span>
                              <span className="text-[11px] text-foreground leading-relaxed">{seg.text}</span>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div className="h-[280px] flex items-center justify-center border rounded-lg">
                          <p className="text-xs text-muted-foreground">타임라인 데이터 없음 — 재처리 필요</p>
                        </div>
                      )
                    ) : (
                      <Textarea readOnly value={fullText} className="h-[280px] font-mono text-[11px] leading-relaxed" placeholder="로딩 중..." />
                    )}
                  </TabsContent>
                  <TabsContent value="ask">
                    <div className="flex flex-col h-[340px]">
                      {/* 채팅 메시지 영역 */}
                      <div className="flex items-center justify-between mb-1">
                        {chatMsgs.length > 0 && (
                          <span className="text-[10px] text-muted-foreground">{chatMsgs.filter(m => m.role === "user").length}개 질문</span>
                        )}
                        {chatMsgs.length > 0 && (
                          <button
                            className="text-[10px] text-muted-foreground hover:text-destructive transition-colors"
                            onClick={() => updateChatMsgs(selected!.id, () => [])}
                          >
                            대화 초기화
                          </button>
                        )}
                      </div>
                      <div className="flex-1 overflow-y-auto space-y-3 pr-1 mb-2">
                        {chatMsgs.length === 0 && (
                          <div className="text-center py-6 text-xs text-muted-foreground">
                            <MessageSquare className="w-6 h-6 mx-auto mb-2 opacity-30" />
                            트랜스크립트 내용에 대해 자유롭게 질문하세요.
                          </div>
                        )}
                        {chatMsgs.map((msg, i) => (
                          <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                            <div className={`max-w-[85%] rounded-lg px-3 py-2 text-[11px] leading-relaxed whitespace-pre-wrap ${
                              msg.role === "user"
                                ? "bg-primary text-primary-foreground"
                                : "bg-muted text-foreground"
                            }`}>
                              {msg.content || (chatLoading && i === chatMsgs.length - 1 ? (
                                <span className="inline-flex gap-0.5">
                                  <span className="animate-bounce">·</span>
                                  <span className="animate-bounce [animation-delay:0.1s]">·</span>
                                  <span className="animate-bounce [animation-delay:0.2s]">·</span>
                                </span>
                              ) : "")}
                            </div>
                          </div>
                        ))}
                        <div ref={chatEndRef} />
                      </div>
                      {/* 입력창 */}
                      <div className="flex gap-1.5 mt-auto">
                        <Input
                          value={chatInput}
                          onChange={e => setChatInput(e.target.value)}
                          onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendQuestion(); } }}
                          placeholder="질문을 입력하세요..."
                          className="text-xs h-8"
                          disabled={chatLoading}
                        />
                        <Button size="icon" className="h-8 w-8 shrink-0" onClick={sendQuestion} disabled={chatLoading || !chatInput.trim()}>
                          {chatLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
                        </Button>
                      </div>
                    </div>
                  </TabsContent>

                  <TabsContent value="slides">
                    {slides.length === 0 ? (
                      <div className="text-center py-6">
                        <ImageIcon className="w-8 h-8 mx-auto mb-2 text-muted-foreground/30" />
                        <p className="text-sm text-muted-foreground">이 영상의 슬라이드 데이터가 없습니다.</p>
                      </div>
                    ) : (
                      <div className="space-y-3">
                        <div className="flex items-center justify-between">
                          <span className="text-xs text-muted-foreground">{slides.length}장 추출됨</span>
                          <a href={`/slides/${selected?.id}`}>
                            <Button variant="outline" size="sm" className="h-7 text-[11px]">
                              <ExternalLink className="w-3 h-3 mr-1" />전체 보기
                            </Button>
                          </a>
                        </div>
                        <div className="grid grid-cols-3 gap-1.5 max-h-[280px] overflow-y-auto">
                          {slides.map((slide) => (
                            <a key={slide.slide_index} href={`/slides/${selected?.id}?slide=${slide.slide_index}`}>
                              <div className="group relative rounded overflow-hidden border hover:border-primary transition-colors cursor-pointer">
                                {/* eslint-disable-next-line @next/next/no-img-element */}
                                <img
                                  src={`${API_BASE}/api/slides/${selected?.id}/image/${slide.filename}`}
                                  alt={`slide ${slide.slide_index}`}
                                  className="w-full aspect-video object-cover"
                                  loading="lazy"
                                />
                                <div className="absolute bottom-0 left-0 right-0 bg-black/60 text-white text-[9px] px-1.5 py-0.5 flex items-center justify-between">
                                  <span className="font-mono">{slide.time_str}</span>
                                  <span className="opacity-50">{slide.slide_index + 1}</span>
                                </div>
                              </div>
                            </a>
                          ))}
                        </div>
                      </div>
                    )}
                  </TabsContent>
                </Tabs>
              </CardContent>
            </Card>
          </div>
        )}
      </div>

      {/* AI 작업 의뢰 모달 */}
      {taskPanelOpen && selectedIds.size >= 1 && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
          onClick={() => setTaskPanelOpen(false)}
        >
          <div
            className="bg-background rounded-xl shadow-2xl w-full max-w-lg mx-4 max-h-[85vh] overflow-y-auto"
            onClick={e => e.stopPropagation()}
          >
            <div className="p-5 space-y-4">
              {/* 헤더 */}
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="font-semibold text-sm flex items-center gap-1.5">
                    <Briefcase className="w-4 h-4 text-primary" />
                    AI 작업 의뢰
                  </h3>
                  <p className="text-[11px] text-muted-foreground mt-1">
                    {Array.from(selectedIds).map(id => items.find(i => i.id === id)?.title).filter(Boolean).slice(0, 2).join(", ")}
                    {selectedIds.size > 2 ? ` 외 ${selectedIds.size - 2}개 영상` : " 영상 선택됨"}
                  </p>
                </div>
                <Button variant="ghost" size="icon" className="h-7 w-7 shrink-0" onClick={() => setTaskPanelOpen(false)}>
                  <X className="w-4 h-4" />
                </Button>
              </div>

              {/* 프리셋 */}
              <div className="flex gap-2 flex-wrap">
                {TASK_PRESETS.map(p => (
                  <Button
                    key={p.label}
                    variant={taskPrompt === p.prompt ? "secondary" : "outline"}
                    size="sm"
                    className="text-[11px]"
                    onClick={() => setTaskPrompt(p.prompt)}
                  >
                    {p.label}
                  </Button>
                ))}
              </div>

              {/* 작업 지시 */}
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-muted-foreground">작업 지시</label>
                <Textarea
                  value={taskPrompt}
                  onChange={e => setTaskPrompt(e.target.value)}
                  placeholder="AI에게 무엇을 만들어달라고 할까요? (요약, 블로그 글, 보고서 등)"
                  className="h-24 text-sm resize-none"
                  autoFocus
                />
              </div>

              {/* 출력 형식 */}
              <div className="flex gap-2 items-center flex-wrap">
                <label className="text-xs font-medium text-muted-foreground shrink-0">출력 형식:</label>
                {[
                  { value: "markdown", label: ".md 파일" },
                  { value: "txt", label: ".txt 파일" },
                  { value: "text", label: "텍스트만" },
                ].map(opt => (
                  <Button
                    key={opt.value}
                    variant={taskOutputType === opt.value ? "secondary" : "outline"}
                    size="sm"
                    className="text-[11px]"
                    onClick={() => setTaskOutputType(opt.value)}
                  >
                    {opt.label}
                  </Button>
                ))}
              </div>

              {/* 모델 */}
              <div className="flex gap-2 items-center flex-wrap">
                <label className="text-xs font-medium text-muted-foreground shrink-0">모델:</label>
                {[
                  { value: "sonnet", label: "Sonnet (빠름)" },
                  { value: "opus", label: "Opus (정밀)" },
                  { value: "haiku", label: "Haiku (경량)" },
                ].map(opt => (
                  <Button
                    key={opt.value}
                    variant={taskModel === opt.value ? "secondary" : "outline"}
                    size="sm"
                    className="text-[11px]"
                    onClick={() => setTaskModel(opt.value)}
                  >
                    {opt.label}
                  </Button>
                ))}
              </div>

              {/* 의뢰 버튼 */}
              <Button
                onClick={submitTask}
                disabled={taskSubmitting || !taskPrompt.trim()}
                className="w-full"
              >
                {taskSubmitting
                  ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" />처리 중...</>
                  : <><Briefcase className="w-4 h-4 mr-2" />작업 의뢰하기</>}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* 다중 영상 AI 질문 패널 */}
      {multiAskOpen && selectedIds.size >= 1 && (
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="text-sm">
                  <Bot className="w-4 h-4 inline mr-1.5 text-primary" />
                  {selectedIds.size}개 영상 종합 AI 질문
                </CardTitle>
                <p className="text-[11px] text-muted-foreground mt-1">
                  {Array.from(selectedIds).map(id => items.find(i => i.id === id)?.title).filter(Boolean).slice(0, 3).join(", ")}
                  {selectedIds.size > 3 ? ` 외 ${selectedIds.size - 3}개` : ""}
                </p>
              </div>
              <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => setMultiAskOpen(false)}>
                <X className="w-4 h-4" />
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            <div className="flex flex-col h-[380px]">
              <div className="flex-1 overflow-y-auto space-y-3 pr-1 mb-3">
                {multiChatMsgs.length === 0 && (
                  <div className="text-center py-8 text-xs text-muted-foreground">
                    <Bot className="w-8 h-8 mx-auto mb-2 opacity-30" />
                    선택한 {selectedIds.size}개 영상의 내용을 종합해서 답변합니다.
                    <br />공통점, 차이점, 핵심 인사이트 등을 질문해보세요.
                  </div>
                )}
                {multiChatMsgs.map((msg, i) => (
                  <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                    <div className={`max-w-[85%] rounded-lg px-3 py-2 text-[12px] leading-relaxed whitespace-pre-wrap ${
                      msg.role === "user"
                        ? "bg-primary text-primary-foreground"
                        : "bg-muted text-foreground"
                    }`}>
                      {msg.content || (multiChatLoading && i === multiChatMsgs.length - 1 ? (
                        <span className="inline-flex gap-0.5">
                          <span className="animate-bounce">·</span>
                          <span className="animate-bounce [animation-delay:0.1s]">·</span>
                          <span className="animate-bounce [animation-delay:0.2s]">·</span>
                        </span>
                      ) : "")}
                    </div>
                  </div>
                ))}
                <div ref={multiChatEndRef} />
              </div>
              <div className="flex gap-2">
                <Input
                  value={multiChatInput}
                  onChange={e => setMultiChatInput(e.target.value)}
                  onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMultiQuestion(); } }}
                  placeholder="여러 영상에 대해 질문하세요..."
                  className="text-sm"
                  disabled={multiChatLoading}
                />
                <Button size="icon" className="shrink-0" onClick={sendMultiQuestion} disabled={multiChatLoading || !multiChatInput.trim()}>
                  {multiChatLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
