"use client";
import { TaskStatus } from "@/lib/types";
import { Progress } from "@/components/ui/progress";
import { Loader2, CheckCircle2, AlertCircle } from "lucide-react";

interface StatusBoxProps {
  status: TaskStatus;
  message: string;
  progress: number;
}

export function StatusBox({ status, message, progress }: StatusBoxProps) {
  return (
    <div
      className={`rounded-lg border p-4 text-sm transition-colors ${
        status === "done"
          ? "border-emerald-200 bg-emerald-50 text-emerald-800"
          : status === "error"
          ? "border-red-200 bg-red-50 text-red-800"
          : status === "running" || status === "pending"
          ? "border-amber-200 bg-amber-50 text-amber-800"
          : "border-muted bg-muted/30 text-muted-foreground"
      }`}
    >
      {(status === "running" || status === "pending") && (
        <Progress value={progress} className="mb-3 h-1.5" />
      )}
      <div className="flex items-center gap-2">
        {(status === "running" || status === "pending") && (
          <Loader2 className="w-4 h-4 animate-spin shrink-0" />
        )}
        {status === "done" && <CheckCircle2 className="w-4 h-4 shrink-0" />}
        {status === "error" && <AlertCircle className="w-4 h-4 shrink-0" />}
        <span className="whitespace-pre-wrap font-mono text-xs leading-relaxed">
          {message || "대기 중..."}
        </span>
      </div>
    </div>
  );
}
