"use client";
export const dynamic = 'force-dynamic';
import { useState } from "react";
import { API_BASE, LANGUAGES, TranscribeResult } from "@/lib/types";
import { useTaskProgress } from "@/lib/useTaskProgress";
import { StatusBox } from "@/components/ui/StatusBox";
import { AdminGuard } from "@/components/AdminGuard";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Copy, Play, Search, Loader2, FolderOpen, Video as VideoIcon, Plus, X, PlayCircle } from "lucide-react";

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

export default function SttPage() {
  const [language, setLanguage] = useState("ko");
  const [minDuration, setMinDuration] = useState(300);
  const [collectionName, setCollectionName] = useState("");

  // 다중 URL 상태
  const [urlEntries, setUrlEntries] = useState<UrlEntry[]>([{ url: "", probe: null, probing: false }]);

  // 단건 STT (첫 번째 단건용)
  const task = useTaskProgress();
  const result = task.result as TranscribeResult | null;

  // 배치 STT
  const batchTask = useTaskProgress();

  // 다중 단건 처리 (여러 URL 동시)
  const multiTasks = [useTaskProgress(), useTaskProgress(), useTaskProgress(), useTaskProgress(), useTaskProgress()];

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

  async function probeAll() {
    await Promise.all(urlEntries.map((_, idx) => probeOne(idx)));
  }

  // 단건들 일괄 처리 (single 타입만)
  async function handleMultiSingle() {
    const singles = urlEntries.filter(e => e.probe?.type === "single" && e.probe.videos[0]);
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

  // 단건 (첫 번째 URL이 single인 경우)
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

  // 다건 배치
  async function handleBatchTranscribe(url: string) {
    try {
      const res = await fetch(`${API_BASE}/api/collections/create`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          url: url.trim(),
          collection_name: collectionName,
          language,
          min_duration: minDuration,
        }),
      });
      const data = await res.json();
      if (data.task_id) batchTask.start(data.task_id);
    } catch { alert("API 연결 실패"); }
  }

  const singleEntries = urlEntries.filter(e => e.probe?.type === "single");
  const hasMultipleSingles = singleEntries.length >= 2;
  const allProbed = urlEntries.every(e => !e.probing && (e.probe !== null || !e.url.trim()));

  return (
    <AdminGuard>
    <div className="space-y-6">
      {/* URL 입력 */}
      <Card>
        <CardHeader>
          <CardTitle>YouTube 영상/채널 분석</CardTitle>
          <CardDescription>단일 또는 여러 YouTube URL을 입력하세요. 채널/재생목록 URL도 지원합니다.</CardDescription>
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
                {/* 단건 probe 결과 인라인 표시 */}
                {entry.probe?.type === "single" && entry.probe.videos[0] && (
                  <Badge variant="outline" className="text-[10px] shrink-0 max-w-[160px] truncate">
                    {entry.probe.videos[0].title}
                  </Badge>
                )}
                {entry.probe?.type === "channel" && (
                  <Badge variant="secondary" className="text-[10px] shrink-0">
                    채널 {entry.probe.total}개
                  </Badge>
                )}
                {entry.probe?.type === "playlist" && (
                  <Badge variant="secondary" className="text-[10px] shrink-0">
                    재생목록 {entry.probe.total}개
                  </Badge>
                )}
              </div>
            ))}
          </div>

          {/* URL 추가 + 전체 스캔 */}
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={addUrl} className="gap-1.5">
              <Plus className="w-3.5 h-3.5" />URL 추가
            </Button>
            {urlEntries.length > 1 && (
              <Button variant="secondary" size="sm" onClick={probeAll} disabled={urlEntries.some(e => e.probing)}>
                {urlEntries.some(e => e.probing) ? (
                  <><Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />스캔 중...</>
                ) : (
                  <><Search className="w-3.5 h-3.5 mr-1.5" />전체 스캔</>
                )}
              </Button>
            )}
          </div>

          {/* 언어 선택 */}
          <div className="flex gap-3">
            <Select value={language} onValueChange={(v) => v && setLanguage(v)}>
              <SelectTrigger className="w-[120px]"><SelectValue /></SelectTrigger>
              <SelectContent>
                {LANGUAGES.map(l => <SelectItem key={l.value} value={l.value}>{l.label}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>

          {/* 여러 단건 영상 일괄 처리 버튼 */}
          {hasMultipleSingles && (
            <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg">
              <p className="text-xs text-blue-700 font-medium mb-2">
                <VideoIcon className="w-3.5 h-3.5 inline mr-1" />
                {singleEntries.length}개 단건 영상 발견
              </p>
              <div className="space-y-1 mb-3 max-h-32 overflow-y-auto">
                {singleEntries.map((e, i) => (
                  <div key={i} className="text-xs text-blue-900 truncate">
                    {i + 1}. {e.probe?.videos[0]?.title} ({fmtDur(e.probe?.videos[0]?.duration || 0)})
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

      {/* 단건/다건 probe 결과 (첫 번째 URL) */}
      {urlEntries[0].probe && !(urlEntries[0].probe.type === "single" && hasMultipleSingles) && (
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center gap-3">
              <Badge variant={urlEntries[0].probe.type === "single" ? "outline" : "default"}>
                {urlEntries[0].probe.type === "single" ? "단건 영상" : urlEntries[0].probe.type === "channel" ? "채널" : "재생목록"}
              </Badge>
              {urlEntries[0].probe.channel && <span className="text-sm text-muted-foreground">@{urlEntries[0].probe.channel}</span>}
              <span className="text-sm font-medium">{urlEntries[0].probe.total}개 영상 발견</span>
              {urlEntries[0].probe.long_form_count !== undefined && urlEntries[0].probe.long_form_count < urlEntries[0].probe.total && (
                <span className="text-xs text-muted-foreground">(롱폼 {urlEntries[0].probe.long_form_count}개)</span>
              )}
            </div>
          </CardHeader>
          <CardContent>
            {urlEntries[0].probe.type === "single" && !hasMultipleSingles ? (
              <div className="space-y-3">
                {urlEntries[0].probe.videos[0] && (
                  <div className="flex items-center gap-3 p-3 bg-muted/50 rounded-lg">
                    <VideoIcon className="w-5 h-5 text-muted-foreground shrink-0" />
                    <div>
                      <p className="text-sm font-medium">{urlEntries[0].probe.videos[0].title}</p>
                      <p className="text-xs text-muted-foreground">{fmtDur(urlEntries[0].probe.videos[0].duration)}</p>
                    </div>
                  </div>
                )}
                <Button onClick={() => handleSingleTranscribe(urlEntries[0].url)} disabled={task.status === "running"} className="w-full" size="lg">
                  <Play className="w-4 h-4 mr-2" />
                  {task.status === "running" ? "변환 중..." : "STT 변환 시작"}
                </Button>
                <Button variant="outline" size="sm" onClick={addUrl} className="w-full gap-1.5 text-muted-foreground">
                  <Plus className="w-3.5 h-3.5" />
                  다른 영상도 함께 분석하기
                </Button>
              </div>
            ) : urlEntries[0].probe.type !== "single" ? (
              <div className="space-y-4">
                <div className="max-h-48 overflow-y-auto space-y-1 border rounded-lg p-2">
                  {urlEntries[0].probe.videos.slice(0, 20).map((v, i) => (
                    <div key={v.id} className="flex items-center gap-2 text-xs py-1 px-2 rounded hover:bg-muted/50">
                      <span className="text-muted-foreground w-6">{i + 1}.</span>
                      <span className="flex-1 truncate">{v.title}</span>
                      <span className="text-muted-foreground shrink-0">{fmtDur(v.duration)}</span>
                      {v.duration >= 300 && <Badge variant="outline" className="text-[8px] px-1">롱폼</Badge>}
                    </div>
                  ))}
                  {urlEntries[0].probe.videos.length > 20 && (
                    <p className="text-xs text-muted-foreground text-center py-2">...외 {urlEntries[0].probe.videos.length - 20}개</p>
                  )}
                </div>
                <div className="flex gap-3 items-end">
                  <div className="flex-1 space-y-1.5">
                    <label className="text-xs font-medium text-muted-foreground">Collection 이름</label>
                    <Input value={collectionName} onChange={(e) => setCollectionName(e.target.value)} />
                  </div>
                  <div className="w-32 space-y-1.5">
                    <label className="text-xs font-medium text-muted-foreground">최소 길이</label>
                    <Select value={String(minDuration)} onValueChange={(v) => setMinDuration(Number(v))}>
                      <SelectTrigger><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="0">전체</SelectItem>
                        <SelectItem value="60">1분+</SelectItem>
                        <SelectItem value="300">5분+ (롱폼)</SelectItem>
                        <SelectItem value="600">10분+</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <Button
                  onClick={() => handleBatchTranscribe(urlEntries[0].url)}
                  disabled={batchTask.status === "running"}
                  className="w-full"
                  size="lg"
                >
                  <FolderOpen className="w-4 h-4 mr-2" />
                  {batchTask.status === "running"
                    ? "배치 처리 중..."
                    : `${minDuration > 0 ? urlEntries[0].probe.videos.filter(v => v.duration >= minDuration).length : urlEntries[0].probe.total}개 영상 배치 STT 시작`}
                </Button>
              </div>
            ) : null}
          </CardContent>
        </Card>
      )}

      {/* 단건 상태 */}
      {task.status !== "idle" && (
        <StatusBox status={task.status} message={task.error || task.message} progress={task.progress} />
      )}

      {/* 다중 단건 상태 */}
      {multiTasks.map((t, i) => t.status !== "idle" && (
        <StatusBox key={i} status={t.status} message={`영상 ${i + 1}: ${t.error || t.message}`} progress={t.progress} />
      ))}

      {/* 배치 상태 */}
      {batchTask.status !== "idle" && (
        <StatusBox status={batchTask.status} message={batchTask.error || batchTask.message} progress={batchTask.progress} />
      )}

      {/* 단건 결과 */}
      {result && (
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="text-base">{result.title}</CardTitle>
                <div className="flex gap-2 mt-2">
                  <Badge variant="secondary">{result.segments} 세그먼트</Badge>
                  <Badge variant="secondary">{result.elapsed.toFixed(1)}초</Badge>
                </div>
              </div>
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
              <TabsContent value="md"><Textarea readOnly value={result.markdown} className="h-80 font-mono text-xs" /></TabsContent>
              <TabsContent value="srt"><Textarea readOnly value={result.srt} className="h-80 font-mono text-xs" /></TabsContent>
              <TabsContent value="raw"><Textarea readOnly value={result.text} className="h-80 font-mono text-xs" /></TabsContent>
            </Tabs>
          </CardContent>
        </Card>
      )}

      {/* 배치 결과 */}
      {batchTask.status === "done" && batchTask.result && (
        <Card>
          <CardContent className="pt-6 text-center">
            <Badge variant="default" className="text-sm px-4 py-1">
              {(batchTask.result as any).done}/{(batchTask.result as any).total}개 완료
            </Badge>
            <p className="text-sm text-muted-foreground mt-2">대시보드에서 결과를 확인하세요.</p>
            <Button variant="outline" size="sm" className="mt-3" onClick={() => window.location.href = "/history"}>
              대시보드로 이동
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
    </AdminGuard>
  );
}
