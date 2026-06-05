"use client";
import { useState } from "react";
import { Copy, Check, Link } from "lucide-react";
import { Button } from "@/components/ui/button";

export function ShareCopyButton({ url }: { url: string }) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    await navigator.clipboard.writeText(url);
    setCopied(true);
    setTimeout(() => setCopied(false), 2500);
  }

  return (
    <Button variant="outline" size="sm" onClick={copy} className="gap-1.5">
      {copied ? <Check className="w-3.5 h-3.5 text-green-600" /> : <Copy className="w-3.5 h-3.5" />}
      {copied ? "복사됨!" : "링크 복사"}
    </Button>
  );
}

export function ShareUrlBar({ url }: { url: string }) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    await navigator.clipboard.writeText(url);
    setCopied(true);
    setTimeout(() => setCopied(false), 2500);
  }

  return (
    <div className="flex items-center gap-2 bg-muted/60 border rounded-lg px-3 py-2">
      <Link className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
      <span className="text-xs text-muted-foreground truncate flex-1">{url}</span>
      <button
        onClick={copy}
        className="shrink-0 text-xs font-medium text-primary hover:underline"
      >
        {copied ? "복사됨!" : "복사"}
      </button>
    </div>
  );
}
