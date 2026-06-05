"use client";
import { useState, useRef } from "react";
import { API_BASE, MODELS, LANGUAGES, TranscribeResult } from "@/lib/types";
import { useTaskProgress } from "@/lib/useTaskProgress";
import { StatusBox } from "@/components/ui/StatusBox";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Upload, Play } from "lucide-react";

export default function FileSttPage() {
  const [language, setLanguage] = useState("ko");
  const [model, setModel] = useState(MODELS[0].value);
  const [fileName, setFileName] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);
  const task = useTaskProgress();
  const result = task.result as TranscribeResult | null;

  async function handleSubmit() {
    const file = fileRef.current?.files?.[0];
    if (!file) return;
    const formData = new FormData();
    formData.append("file", file);
    formData.append("language", language);
    formData.append("model", model);
    try {
      const res = await fetch(`${API_BASE}/api/transcribe/file`, { method: "POST", body: formData });
      const data = await res.json();
      if (data.task_id) task.start(data.task_id);
    } catch { alert("API 연결 실패"); }
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>로컬 파일 STT 변환</CardTitle>
          <CardDescription>오디오/비디오 파일을 업로드하여 텍스트로 변환합니다.</CardDescription>
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
            <Select value={language} onValueChange={(v) => v && setLanguage(v)}>
              <SelectTrigger className="flex-1"><SelectValue /></SelectTrigger>
              <SelectContent>
                {LANGUAGES.map(l => <SelectItem key={l.value} value={l.value}>{l.label}</SelectItem>)}
              </SelectContent>
            </Select>
            <Select value={model} onValueChange={(v) => v && setModel(v)}>
              <SelectTrigger className="flex-[2]"><SelectValue /></SelectTrigger>
              <SelectContent>
                {MODELS.map(m => <SelectItem key={m.value} value={m.value}>{m.label}</SelectItem>)}
              </SelectContent>
            </Select>
            <Button onClick={handleSubmit} disabled={task.status === "running"} className="flex-1" size="lg">
              <Play className="w-4 h-4 mr-2" />
              변환 시작
            </Button>
          </div>
        </CardContent>
      </Card>

      <StatusBox status={task.status} message={task.error || task.message} progress={task.progress} />

      {result && (
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center gap-2">
              <CardTitle className="text-base">변환 결과</CardTitle>
              <Badge variant="secondary">{result.segments} 세그먼트</Badge>
              <Badge variant="secondary">{result.elapsed.toFixed(1)}초</Badge>
            </div>
          </CardHeader>
          <CardContent>
            <Textarea readOnly value={result.markdown} className="h-80 font-mono text-xs" />
          </CardContent>
        </Card>
      )}
    </div>
  );
}
