"use client";
import { useEffect, useState, useRef } from "react";
import { useParams, useSearchParams } from "next/navigation";
import Link from "next/link";
import { API_BASE } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { ChevronLeft, ChevronRight, Search, ExternalLink, ArrowLeft, Trash2 } from "lucide-react";

interface Slide {
  slide_index: number;
  timestamp: number;
  time_str: string;
  filename: string;
  ocr_text: string;
}

interface VideoMeta {
  video_id: string;
  title: string;
  url: string;
  total_slides: number;
  extracted_at: string;
  slides: Slide[];
}

export default function SlideViewerClient() {
  const params = useParams();
  const searchParams = useSearchParams();
  const vid_id = params.vid_id as string;

  const [meta, setMeta] = useState<VideoMeta | null>(null);
  const [current, setCurrent] = useState(0);
  const [filter, setFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const thumbRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetch(`${API_BASE}/api/slides/${vid_id}`)
      .then((r) => r.json())
      .then((data) => {
        setMeta(data);
        const slideParam = searchParams.get("slide");
        if (slideParam !== null) setCurrent(parseInt(slideParam, 10));
      })
      .finally(() => setLoading(false));
  }, [vid_id, searchParams]);

  // 썸네일 스크롤 동기화
  useEffect(() => {
    const el = thumbRef.current?.children[current] as HTMLElement;
    el?.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "center" });
  }, [current]);

  if (loading) return <div className="p-8 text-muted-foreground">불러오는 중...</div>;
  if (!meta) return <div className="p-8 text-destructive">영상을 찾을 수 없습니다.</div>;

  const filteredSlides = filter.trim()
    ? meta.slides.filter((s) => s.ocr_text.toLowerCase().includes(filter.toLowerCase()))
    : meta.slides;

  const slide = meta.slides[current];
  const imgUrl = `${API_BASE}/api/slides/${vid_id}/image/${slide.filename}`;

  function goTo(idx: number) {
    setCurrent(Math.max(0, Math.min(meta!.slides.length - 1, idx)));
  }

  async function deleteSlide(slideIndex: number) {
    if (!confirm(`슬라이드 ${slideIndex + 1}번을 삭제하시겠습니까?`)) return;
    const res = await fetch(`${API_BASE}/api/slides/${vid_id}/slide/${slideIndex}`, { method: "DELETE" });
    if (!res.ok) { alert("삭제 실패"); return; }
    const remaining = meta!.slides.filter((s) => s.slide_index !== slideIndex);
    setMeta({ ...meta!, slides: remaining, total_slides: remaining.length });
    if (current >= remaining.length) setCurrent(Math.max(0, remaining.length - 1));
  }

  return (
    <div className="max-w-6xl mx-auto px-6 py-6 space-y-4">
      {/* 상단 */}
      <div className="flex items-start gap-3">
        <Link href="/slides" className="mt-1 text-muted-foreground hover:text-foreground">
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <div className="flex-1 min-w-0">
          <h1 className="text-lg font-bold truncate">{meta.title}</h1>
          <div className="flex items-center gap-2 mt-0.5">
            <Badge variant="secondary">{meta.total_slides}장</Badge>
            {meta.url && (
              <a href={meta.url} target="_blank" rel="noopener noreferrer"
                className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1">
                YouTube <ExternalLink className="w-3 h-3" />
              </a>
            )}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_280px] gap-4">
        {/* 메인 뷰어 */}
        <div className="space-y-3">
          <div className="relative bg-zinc-950 rounded-lg overflow-hidden aspect-video flex items-center justify-center">
            <img src={imgUrl} alt={`slide ${current}`} className="max-w-full max-h-full object-contain" />
            <button
              onClick={() => goTo(current - 1)}
              disabled={current === 0}
              className="absolute left-2 top-1/2 -translate-y-1/2 bg-black/50 hover:bg-black/70 disabled:opacity-20 rounded-full p-1.5 transition"
            >
              <ChevronLeft className="w-5 h-5 text-white" />
            </button>
            <button
              onClick={() => goTo(current + 1)}
              disabled={current === meta.slides.length - 1}
              className="absolute right-2 top-1/2 -translate-y-1/2 bg-black/50 hover:bg-black/70 disabled:opacity-20 rounded-full p-1.5 transition"
            >
              <ChevronRight className="w-5 h-5 text-white" />
            </button>
            <div className="absolute bottom-2 right-3 bg-black/60 text-white text-xs px-2 py-0.5 rounded">
              {current + 1} / {meta.slides.length} · {slide.time_str}
            </div>
            <button
              onClick={() => deleteSlide(slide.slide_index)}
              className="absolute top-2 right-2 bg-black/50 hover:bg-red-600/80 rounded-full p-1.5 transition"
              title="이 슬라이드 삭제"
            >
              <Trash2 className="w-4 h-4 text-white" />
            </button>
          </div>

          {/* OCR 텍스트 */}
          {slide.ocr_text && (
            <div className="bg-zinc-950 text-zinc-300 font-mono text-xs p-3 rounded max-h-32 overflow-auto border border-zinc-800">
              {slide.ocr_text}
            </div>
          )}

          {/* 썸네일 스트립 */}
          <div ref={thumbRef} className="flex gap-1.5 overflow-x-auto pb-1 scroll-smooth">
            {meta.slides.map((s, i) => (
              <button
                key={s.slide_index}
                onClick={() => setCurrent(i)}
                className={`shrink-0 rounded overflow-hidden border-2 transition-all ${
                  i === current ? "border-primary" : "border-transparent hover:border-muted"
                }`}
              >
                <img
                  src={`${API_BASE}/api/slides/${vid_id}/image/${s.filename}`}
                  alt={`thumb ${i}`}
                  className="w-24 h-14 object-cover"
                  loading="lazy"
                />
              </button>
            ))}
          </div>
        </div>

        {/* 사이드 패널: 슬라이드 목록 + 검색 */}
        <div className="space-y-2">
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
            <Input
              className="pl-8 text-sm h-8"
              placeholder="이 영상에서 검색..."
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
            />
          </div>
          <div className="space-y-0.5 max-h-[500px] overflow-y-auto border rounded-lg">
            {filteredSlides.length === 0 && (
              <p className="p-3 text-xs text-muted-foreground">검색 결과 없음</p>
            )}
            {filteredSlides.map((s) => (
              <div
                key={s.slide_index}
                className={`flex gap-2 p-2 border-b last:border-0 hover:bg-muted/50 transition-colors group ${
                  s.slide_index === current ? "bg-primary/5" : ""
                }`}
              >
                <button
                  onClick={() => { setCurrent(s.slide_index); setFilter(""); }}
                  className="flex gap-2 flex-1 text-left min-w-0"
                >
                  <img
                    src={`${API_BASE}/api/slides/${vid_id}/image/${s.filename}`}
                    alt=""
                    className="w-16 h-10 object-cover rounded shrink-0 bg-zinc-100"
                    loading="lazy"
                  />
                  <div className="min-w-0">
                    <div className="text-xs font-medium">{s.slide_index + 1}번 · {s.time_str}</div>
                    <div className="text-xs text-muted-foreground line-clamp-2 mt-0.5">{s.ocr_text || "텍스트 없음"}</div>
                  </div>
                </button>
                <button
                  onClick={() => deleteSlide(s.slide_index)}
                  className="opacity-0 group-hover:opacity-100 shrink-0 p-1 text-muted-foreground hover:text-red-500 transition"
                  title="삭제"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
