"use client";
import { useState, useRef, useEffect } from "react";
import { API_BASE, MODELS, LANGUAGES, TranscribeResult } from "@/lib/types";
import { useTaskProgress } from "@/lib/useTaskProgress";
import { StatusBox } from "@/components/ui/StatusBox";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import {
  X, Copy, Play, Search, Loader2, FolderOpen,
  Video as VideoIcon, Upload, Mic, Plus, PlayCircle,
} from "lucide-react";

interface ProbeResult {
  type: "single" | "channel" | "playlist" | "unknown";
  url: string;
  channel: string;
  videos: { id: string; title: string; duration: number }[];
  total: number;
  long_form_count?: number;
}

interface UrlEntry {
  url: string;
  probe: ProbeResult | null;
  probing: boolean;
}

function fmtDur(sec: number) {
  const m = Math.floor(sec / 60);
  return m >= 60 ? `${Math.floor(m / 60)}시간 ${m % 60}분` : `${m}분`;
}

function isSingleVideo(url: string) {
  return /youtu\.be\/[a-zA-Z0-9_-]{11}|youtube\.com\/watch\?v=[a-zA-Z0-9_-]{11}/.test(url);
}

interface SttLayerProps {
  open: boolean;
  onClose: () => void;
  onTaskDone: () => void;
}

export function SttLayer({ open, onClose, onTaskDone }: SttLayerProps) {
  const [activeTab, setActiveTab] = useState<"youtube" | "file">("youtube");

  // YouTube STT state — multi-URL
  const [urlEntries, setUrlEntries] = useState<UrlEntry[]>([{ url: "", probe: null, probing: false }]);
  const [language, setLanguage] = useState("ko");
  const [minDuration, setMinDuration] = useState(300);
  const [collectionName, setCollectionName] = useState("");

  const task = useTaskProgress();
  const result = task.result as TranscribeResult | null;
  const batchTask = useTaskProgress();
  const multiTasks = [useTaskProgress(), useTaskProgress(), useTaskProgress(), useTaskProgress(), useTaskProgress()];

  // File STT state
  const [fileLanguage, setFileLanguage] = useState("ko");
  const [fileModel, setFileModel] = useState(MODELS[0].value);
  const [fileName, setFileName] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);
  const fileTask = useTaskProgress();
  const fileResult = fileTask.result as TranscribeResult | null;

  // Notify dashboard when any task completes
  useEffect(() => {
    const allStatuses = [task.status, batchTask.status, fileTask.status, ...multiTasks.map(t => t.status)];
    if (allStatuses.some(s => s === "done")) onTaskDone();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [task.status, batchTask.status, fileTask.status, ...multiTasks.map(t => t.status)]);

  // ESC to close
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, onClose]);

  function addUrl() {
    setUrlEntries(prev => [...prev, { url: "", probe: null, probing: false }]);
  }

  function removeUrl(idx: number) {
    setUrlEntries(prev => prev.filter((_, i) => i !== idx));
  }

  function updateUrl(idx: number, url: string) {
    setUrlEntries(prev => prev.map((e, i) => i === idx ? { ...e, url, probe: null } : e));
  }

  async function probeOne(idx: number) {
    const entry = urlEntries[idx];
    if (!entry.url.trim()) return;
    setUrlEntries(prev => prev.map((e, i) => i === idx ? { ...e, probing: true, probe: null } : e));
    try {
      const res = await fetch(`${API_BASE}/api/probe`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: entry.url.trim() }),
      });
      const data: ProbeResult = await res.json();
      setUrlEntries(prev => prev.map((e, i) => i === idx ? { ...e, probing: false, probe: data } : e));
      if (data.type !== "single" && data.channel && idx === 0) {
        setCollectionName(`${data.channel} 채널 분석`);
      }
    } catch {
      setUrlEntries(prev => prev.map((e, i) => i === idx ? { ...e, probing: false } : e));
      alert("API 연결 실패. Python 백엔드(port 9102) 확인하세요.");
    }
  }

  async function handleSingleTranscribe(url: string) {
    try {
      const res = await fetch(`${API_BASE}/api/transcribe/youtube`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: url.trim(), language }),
      });
      const data = await res.json();
      if (data.task_id) task.start(data.task_id);
    } catch { alert("API 연결 실패"); }
  }

  async function handleMultiSingle() {
    const singles = urlEntries.filter(e =>
      (e.probe?.type === "single" && e.probe.videos[0]) ||
      (e.probe?.type === "unknown" && isSingleVideo(e.url)) ||
      (!e.probe && isSingleVideo(e.url))
    );
    for (let i = 0; i < Math.min(singles.length, 5); i++) {
      const entry = singles[i];
      try {
        const res = await fetch(`${API_BASE}/api/transcribe/youtube`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ url: entry.url.trim(), language }),
        });
        const data = await res.json();
        if (data.task_id) multiTasks[i].start(data.task_id);
      } catch { alert(`API 연결 실패: ${entry.url}`); }
    }
  }

  async function handleBatchTranscribe(url: string) {
    try {
      const res = await fetch(`${API_BASE}/api/collections/create`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: url.trim(), collection_name: collectionName, language, min_duration: minDuration }),
      });
      const data = await res.json();
      if (data.task_id) batchTask.start(data.task_id);
    } catch { alert("API 연결 실패"); }
  }

  async function handleFileSubmit() {
    const file = fileRef.current?.files?.[0];
    if (!file) return;
    const formData = new FormData();
    formData.append("file", file);
    formData.append("language", fileLanguage);
    formData.append("model", fileModel);
    try {
      const res = await fetch(`${API_BASE}/api/transcribe/file`, { method: "POST", body: formData });
      const data = await res.json();
      if (data.task_id) fileTask.start(data.task_id);
    } catch { alert("API 연결 실패"); }
  }

  const singleEntries = urlEntries.filter(e =>
    (e.probe?.type === "single" && e.probe.videos[0]) ||
    (e.probe?.type === "unknown" && isSingleVideo(e.url)) ||
    (!e.probe && isSingleVideo(e.url))
  );
  const hasMultipleSingles = singleEntries.length >= 2;
  const firstProbe = urlEntries[0].probe;

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center">
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={onClose} />

      <div className="relative z-10 w-full max-w-3xl mt-12 mb-12 max-h-[calc(100vh-6rem)] overflow-y-auto bg-background rounded-2xl shadow-2xl border animate-in fade-in slide-in-from-bottom-4 duration-200">
        {/* header */}
        <div className="sticky top-0 z-20 bg-background/95 backdrop-blur border-b px-6 py-4 flex items-center justify-between rounded-t-2xl">
          <div className="flex items-center gap-3">
            <Mic className="w-5 h-5 text-primary" />
            <h2 className="text-lg font-semibold">STT 변환</h2>
          </div>
          <Button variant="ghost" size="icon" className="h-8 w-8" onClick={onClose}>
            <X className="w-4 h-4" />
          </Button>
        </div>

        <div className="p-6">
          <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as "youtube" | "file")}>
            <TabsList className="w-full mb-6">
              <TabsTrigger value="youtube" className="flex-1 gap-2">
                <VideoIcon className="w-4 h-4" />YouTube 영상
              </TabsTrigger>
              <TabsTrigger value="file" className="flex-1 gap-2">
                <Upload className="w-4 h-4" />파일 업로드
              </TabsTrigger>
            </TabsList>

            {/* ─── YouTube STT Tab ─── */}
            <TabsContent value="youtube" className="space-y-4">
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-base">YouTube 영상/채널 분석</CardTitle>
                  <CardDescription className="text-xs">단일 영상, 채널, 재생목록 URL 모두 지원. 여러 URL 동시 분석 가능.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  {/* URL 목록 */}
                  <div className="space-y-2">
                    {urlEntries.map((entry, idx) => (
                      <div key={idx} className="flex gap-2 items-center">
                        <div className="flex-1 flex gap-2">
                          <Input
                            value={entry.url}
                            onChange={(e) => updateUrl(idx, e.target.value)}
                            placeholder={idx === 0 ? "https://youtu.be/... 또는 채널/재생목록 URL" : `URL ${idx + 1}`}
                            className="flex-1"
                            onKeyDown={(e) => e.key === "Enter" && probeOne(idx)}
                          />
                          <Button
                            onClick={() => probeOne(idx)}
                            disabled={entry.probing || !entry.url.trim()}
                            variant="secondary"
                            size="sm"
                            className="shrink-0"
                          >
                            {entry.probing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
                          </Button>
                        </div>
                        {idx > 0 && (
                          <Button variant="ghost" size="icon" className="h-9 w-9 shrink-0" onClick={() => removeUrl(idx)}>
                            <X className="w-4 h-4" />
                          </Button>
                        )}
                        {entry.probe?.type === "single" && entry.probe.videos[0] && (
                          <Badge variant="outline" className="text-[10px] shrink-0 max-w-[140px] truncate">
                            {entry.probe.videos[0].title}
                          </Badge>
                        )}
                        {entry.probe?.type === "channel" && (
                          <Badge variant="secondary" className="text-[10px] shrink-0">채널 {entry.probe.total}개</Badge>
                        )}
                        {entry.probe?.type === "playlist" && (
                          <Badge variant="secondary" className="text-[10px] shrink-0">재생목록 {entry.probe.total}개</Badge>
                        )}
                        {entry.probe?.type === "unknown" && (
                          <Badge variant="destructive" className="text-[10px] shrink-0">정보 조회 실패</Badge>
                        )}
                      </div>
                    ))}
                  </div>

                  {/* URL 추가 + 언어 */}
                  <div className="flex gap-2 items-center">
                    <Button variant="outline" size="sm" onClick={addUrl} className="gap-1.5">
                      <Plus className="w-3.5 h-3.5" />URL 추가
                    </Button>
                    <Select value={language} onValueChange={(v) => v && setLanguage(v)}>
                      <SelectTrigger className="w-[100px]"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {LANGUAGES.map(l => <SelectItem key={l.value} value={l.value}>{l.label}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>

                  {/* 단건 URL이고 probe가 없거나 실패한 경우 바로 변환 버튼 표시 */}
                  {!hasMultipleSingles && isSingleVideo(urlEntries[0].url) &&
                    (!urlEntries[0].probe || urlEntries[0].probe.type === "unknown") && (
                    <Button
                      onClick={() => handleSingleTranscribe(urlEntries[0].url)}
                      disabled={task.status === "running"}
                      className="w-full"
                      size="lg"
                    >
                      <Play className="w-4 h-4 mr-2" />
                      {task.status === "running" ? "변환 중..." : "STT 변환 시작"}
                    </Button>
                  )}

                  {/* 다중 단건 일괄 처리 */}
                  {hasMultipleSingles && (
                    <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg">
                      <p className="text-xs text-blue-700 font-medium mb-2">
                        <VideoIcon className="w-3.5 h-3.5 inline mr-1" />
                        {singleEntries.length}개 단건 영상 동시 분석
                      </p>
                      <div className="space-y-1 mb-3 max-h-28 overflow-y-auto">
                        {singleEntries.map((e, i) => (
                          <div key={i} className="text-xs text-blue-900 truncate">
                            {i + 1}. {e.probe?.videos[0]?.title
                              ? `${e.probe.videos[0].title} (${fmtDur(e.probe.videos[0].duration)})`
                              : e.url}
                          </div>
                        ))}
                      </div>
                      <Button
                        onClick={handleMultiSingle}
                        disabled={multiTasks.some(t => t.status === "running")}
                        className="w-full"
                        size="sm"
                      >
                        <PlayCircle className="w-4 h-4 mr-2" />
                        {singleEntries.length}개 영상 동시 STT 변환 시작
                      </Button>
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* 단건/채널 probe 결과 (첫 번째 URL, hasMultipleSingles가 아닐 때만, unknown 제외) */}
              {firstProbe && firstProbe.type !== "unknown" && !(firstProbe.type === "single" && hasMultipleSingles) && (
                <Card>
                  <CardHeader className="pb-3">
                    <div className="flex items-center gap-3">
                      <Badge variant={firstProbe.type === "single" ? "outline" : "default"}>
                        {firstProbe.type === "single" ? "단건 영상" : firstProbe.type === "channel" ? "채널" : "재생목록"}
                      </Badge>
                      {firstProbe.channel && <span className="text-sm text-muted-foreground">@{firstProbe.channel}</span>}
                      <span className="text-sm font-medium">{firstProbe.total}개 영상</span>
                    </div>
                  </CardHeader>
                  <CardContent>
                    {firstProbe.type === "single" ? (
                      <div className="space-y-3">
                        {firstProbe.videos[0] && (
                          <div className="flex items-center gap-3 p-3 bg-muted/50 rounded-lg">
                            <VideoIcon className="w-5 h-5 text-muted-foreground shrink-0" />
                            <div>
                              <p className="text-sm font-medium">{firstProbe.videos[0].title}</p>
                              <p className="text-xs text-muted-foreground">{fmtDur(firstProbe.videos[0].duration)}</p>
                            </div>
                          </div>
                        )}
                        <Button onClick={() => handleSingleTranscribe(urlEntries[0].url)} disabled={task.status === "running"} className="w-full" size="lg">
                          <Play className="w-4 h-4 mr-2" />
                          {task.status === "running" ? "변환 중..." : "STT 변환 시작"}
                        </Button>
                        <Button variant="outline" size="sm" onClick={addUrl} className="w-full gap-1.5 text-muted-foreground">
                          <Plus className="w-3.5 h-3.5" />다른 영상도 함께 분석하기
                        </Button>
                      </div>
                    ) : (
                      <div className="space-y-4">
                        <div className="max-h-40 overflow-y-auto space-y-1 border rounded-lg p-2">
                          {firstProbe.videos.slice(0, 20).map((v, i) => (
                            <div key={v.id} className="flex items-center gap-2 text-xs py-1 px-2 rounded hover:bg-muted/50">
                              <span className="text-muted-foreground w-6">{i + 1}.</span>
                              <span className="flex-1 truncate">{v.title}</span>
                              <span className="text-muted-foreground shrink-0">{fmtDur(v.duration)}</span>
                              {v.duration >= 300 && <Badge variant="outline" className="text-[8px] px-1">롱폼</Badge>}
                            </div>
                          ))}
                          {firstProbe.videos.length > 20 && (
                            <p className="text-xs text-muted-foreground text-center py-2">...외 {firstProbe.videos.length - 20}개</p>
                          )}
                        </div>
                        <div className="flex gap-3 items-end">
                          <div className="flex-1 space-y-1.5">
                            <label className="text-xs font-medium text-muted-foreground">Collection 이름</label>
                            <Input value={collectionName} onChange={(e) => setCollectionName(e.target.value)} />
                          </div>
                          <div className="w-28 space-y-1.5">
                            <label className="text-xs font-medium text-muted-foreground">최소 길이</label>
                            <Select value={String(minDuration)} onValueChange={(v) => setMinDuration(Number(v))}>
                              <SelectTrigger><SelectValue /></SelectTrigger>
                              <SelectContent>
                                <SelectItem value="0">전체</SelectItem>
                                <SelectItem value="60">1분+</SelectItem>
                                <SelectItem value="300">5분+</SelectItem>
                                <SelectItem value="600">10분+</SelectItem>
                              </SelectContent>
                            </Select>
                          </div>
                        </div>
                        <Button onClick={() => handleBatchTranscribe(urlEntries[0].url)} disabled={batchTask.status === "running"} className="w-full" size="lg">
                          <FolderOpen className="w-4 h-4 mr-2" />
                          {batchTask.status === "running"
                            ? "배치 처리 중..."
                            : `${minDuration > 0 ? firstProbe.videos.filter(v => v.duration >= minDuration).length : firstProbe.total}개 영상 배치 STT 시작`}
                        </Button>
                      </div>
                    )}
                  </CardContent>
                </Card>
              )}

              {task.status !== "idle" && (
                <StatusBox status={task.status} message={task.error || task.message} progress={task.progress} />
              )}
              {multiTasks.map((t, i) => t.status !== "idle" && (
                <div key={i} className="space-y-2">
                  <StatusBox status={t.status} message={`영상 ${i + 1}: ${t.error || t.message}`} progress={t.progress} />
                  {t.status === "done" && t.result && (() => {
                    const r = t.result as any;
                    return (
                      <Card>
                        <CardHeader className="pb-3">
                          <CardTitle className="text-base">{r.title}</CardTitle>
                          <div className="flex flex-wrap gap-2 mt-1">
                            <Badge variant="secondary">{r.segments} 세그먼트</Badge>
                            {r.elapsed != null && <Badge variant="secondary">{r.elapsed.toFixed(1)}초</Badge>}
                            {r.slides != null && r.slides > 0 && (
                              <a href={`/slides/${r.video_id}`} target="_blank" rel="noreferrer">
                                <Badge variant="secondary" className="cursor-pointer hover:bg-blue-100 hover:text-blue-700 transition-colors">
                                  🖼 슬라이드 {r.slides}장 →
                                </Badge>
                              </a>
                            )}
                            {r.slides_error && (
                              <Badge variant="destructive" title={r.slides_error}>슬라이드 추출 실패</Badge>
                            )}
                          </div>
                        </CardHeader>
                        <CardContent>
                          <Tabs defaultValue="md">
                            <div className="flex items-center justify-between mb-3">
                              <TabsList>
                                <TabsTrigger value="md">마크다운</TabsTrigger>
                                <TabsTrigger value="srt">SRT</TabsTrigger>
                                <TabsTrigger value="raw">원본</TabsTrigger>
                              </TabsList>
                              <Button variant="ghost" size="sm" onClick={() => navigator.clipboard.writeText(r.markdown)}>
                                <Copy className="w-3.5 h-3.5 mr-1.5" />복사
                              </Button>
                            </div>
                            <TabsContent value="md"><Textarea readOnly value={r.markdown} className="h-48 font-mono text-xs" /></TabsContent>
                            <TabsContent value="srt"><Textarea readOnly value={r.srt} className="h-48 font-mono text-xs" /></TabsContent>
                            <TabsContent value="raw"><Textarea readOnly value={r.text} className="h-48 font-mono text-xs" /></TabsContent>
                          </Tabs>
                        </CardContent>
                      </Card>
                    );
                  })()}
                </div>
              ))}
              {batchTask.status !== "idle" && (
                <StatusBox status={batchTask.status} message={batchTask.error || batchTask.message} progress={batchTask.progress} />
              )}

              {result && (
                <Card>
                  <CardHeader className="pb-3">
                    <CardTitle className="text-base">{result.title}</CardTitle>
                    <div className="flex flex-wrap gap-2 mt-1">
                      <Badge variant="secondary">{result.segments} 세그먼트</Badge>
                      {result.elapsed != null && <Badge variant="secondary">{result.elapsed.toFixed(1)}초</Badge>}
                      {result.slides != null && result.slides > 0 && (
                        <a href={`/slides/${result.video_id}`} target="_blank" rel="noreferrer">
                          <Badge variant="secondary" className="cursor-pointer hover:bg-blue-100 hover:text-blue-700 transition-colors">
                            🖼 슬라이드 {result.slides}장 →
                          </Badge>
                        </a>
                      )}
                      {result.slides_error && (
                        <Badge variant="destructive" title={result.slides_error}>슬라이드 추출 실패</Badge>
                      )}
                    </div>
                  </CardHeader>
                  <CardContent>
                    <Tabs defaultValue="md">
                      <div className="flex items-center justify-between mb-3">
                        <TabsList>
                          <TabsTrigger value="md">마크다운</TabsTrigger>
                          <TabsTrigger value="srt">SRT</TabsTrigger>
                          <TabsTrigger value="raw">원본</TabsTrigger>
                        </TabsList>
                        <Button variant="ghost" size="sm" onClick={() => navigator.clipboard.writeText(result.markdown)}>
                          <Copy className="w-3.5 h-3.5 mr-1.5" />복사
                        </Button>
                      </div>
                      <TabsContent value="md"><Textarea readOnly value={result.markdown} className="h-60 font-mono text-xs" /></TabsContent>
                      <TabsContent value="srt"><Textarea readOnly value={result.srt} className="h-60 font-mono text-xs" /></TabsContent>
                      <TabsContent value="raw"><Textarea readOnly value={result.text} className="h-60 font-mono text-xs" /></TabsContent>
                    </Tabs>
                  </CardContent>
                </Card>
              )}

              {batchTask.status === "done" && batchTask.result && (
                <Card>
                  <CardContent className="pt-6 text-center">
                    <Badge variant="default" className="text-sm px-4 py-1">
                      {(batchTask.result as any).done}/{(batchTask.result as any).total}개 완료
                    </Badge>
                    <p className="text-sm text-muted-foreground mt-2">대시보드에 자동 반영됩니다.</p>
                  </CardContent>
                </Card>
              )}
            </TabsContent>

            {/* ─── File STT Tab ─── */}
            <TabsContent value="file" className="space-y-4">
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-base">로컬 파일 STT 변환</CardTitle>
                  <CardDescription className="text-xs">오디오/비디오 파일을 업로드하여 텍스트로 변환</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div
                    onClick={() => fileRef.current?.click()}
                    className="border-2 border-dashed rounded-xl p-8 text-center cursor-pointer hover:border-primary/50 hover:bg-muted/50 transition-colors"
                  >
                    <Upload className="w-8 h-8 mx-auto text-muted-foreground mb-2" />
                    <p className="text-sm font-medium">{fileName || "파일을 선택하거나 드래그하세요"}</p>
                    <p className="text-xs text-muted-foreground mt-1">.mp3, .wav, .m4a, .mp4, .webm</p>
                    <input
                      ref={fileRef}
                      type="file"
                      accept="audio/*,video/*,.mp3,.wav,.m4a,.mp4,.webm"
                      onChange={(e) => setFileName(e.target.files?.[0]?.name || "")}
                      className="hidden"
                    />
                  </div>
                  <div className="flex gap-3">
                    <Select value={fileLanguage} onValueChange={(v) => v && setFileLanguage(v)}>
                      <SelectTrigger className="flex-1"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {LANGUAGES.map(l => <SelectItem key={l.value} value={l.value}>{l.label}</SelectItem>)}
                      </SelectContent>
                    </Select>
                    <Select value={fileModel} onValueChange={(v) => v && setFileModel(v)}>
                      <SelectTrigger className="flex-[2]"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {MODELS.map(m => <SelectItem key={m.value} value={m.value}>{m.label}</SelectItem>)}
                      </SelectContent>
                    </Select>
                    <Button onClick={handleFileSubmit} disabled={fileTask.status === "running"} className="flex-1" size="lg">
                      <Play className="w-4 h-4 mr-2" />변환 시작
                    </Button>
                  </div>
                </CardContent>
              </Card>

              {fileTask.status !== "idle" && (
                <StatusBox status={fileTask.status} message={fileTask.error || fileTask.message} progress={fileTask.progress} />
              )}

              {fileResult && (
                <Card>
                  <CardHeader className="pb-3">
                    <div className="flex items-center gap-2">
                      <CardTitle className="text-base">변환 결과</CardTitle>
                      <Badge variant="secondary">{fileResult.segments} 세그먼트</Badge>
                      <Badge variant="secondary">{fileResult.elapsed.toFixed(1)}초</Badge>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="flex justify-end mb-2">
                      <Button variant="ghost" size="sm" onClick={() => navigator.clipboard.writeText(fileResult.markdown)}>
                        <Copy className="w-3.5 h-3.5 mr-1.5" />복사
                      </Button>
                    </div>
                    <Textarea readOnly value={fileResult.markdown} className="h-60 font-mono text-xs" />
                  </CardContent>
                </Card>
              )}
            </TabsContent>
          </Tabs>
        </div>
      </div>
    </div>
  );
}
