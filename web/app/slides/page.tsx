"use client";
export const dynamic = 'force-dynamic';
import { useEffect, useState } from "react";
import Link from "next/link";
import { API_BASE } from "@/lib/types";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Search, Images, ExternalLink } from "lucide-react";

interface VideoItem {
  vid_id: string;
  title: string;
  url: string;
  total_slides: number;
  extracted_at: string;
  thumbnail: string | null;
}

interface SearchResult {
  vid_id: string;
  title: string;
  slide_index: number;
  filename: string;
  time_str: string;
  ocr_text: string;
  match_excerpt: string;
}

export default function SlidesPage() {
  const [videos, setVideos] = useState<VideoItem[]>([]);
  const [query, setQuery] = useState("");
  const [searchResults, setSearchResults] = useState<SearchResult[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API_BASE}/api/slides`)
      .then((r) => r.json())
      .then(setVideos)
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!query.trim()) {
      setSearchResults(null);
      return;
    }
    const timer = setTimeout(async () => {
      setSearching(true);
      try {
        const r = await fetch(`${API_BASE}/api/slides/search?q=${encodeURIComponent(query)}`);
        setSearchResults(await r.json());
      } finally {
        setSearching(false);
      }
    }, 400);
    return () => clearTimeout(timer);
  }, [query]);

  const totalSlides = videos.reduce((s, v) => s + v.total_slides, 0);

  return (
    <div className="max-w-6xl mx-auto px-6 py-8 space-y-6">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Images className="w-6 h-6" /> 슬라이드 라이브러리
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            {videos.length}개 영상 · {totalSlides}장 슬라이드 · OCR 텍스트 검색 (무료)
          </p>
        </div>
      </div>

      {/* 검색 바 */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
        <Input
          className="pl-9"
          placeholder="슬라이드 내 텍스트 검색..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>

      {/* 검색 결과 */}
      {query.trim() && (
        <div className="space-y-2">
          <h2 className="text-sm font-semibold text-muted-foreground">
            {searching ? "검색 중..." : `검색 결과 ${searchResults?.length ?? 0}건`}
          </h2>
          {searchResults?.map((r, i) => (
            <Link
              key={i}
              href={`/slides/${r.vid_id}?slide=${r.slide_index}`}
              className="flex gap-3 p-3 border rounded-lg hover:bg-muted/50 transition-colors"
            >
              <img
                src={`${API_BASE}/api/slides/${r.vid_id}/image/${r.filename}`}
                alt={`slide ${r.slide_index}`}
                className="w-24 h-14 object-cover rounded shrink-0 bg-zinc-100"
              />
              <div className="min-w-0">
                <div className="text-xs font-medium text-muted-foreground truncate">{r.title}</div>
                <div className="text-xs text-muted-foreground">슬라이드 {r.slide_index + 1} · {r.time_str}</div>
                <div className="text-sm mt-1 text-foreground line-clamp-2">{r.match_excerpt}</div>
              </div>
            </Link>
          ))}
          {searchResults?.length === 0 && !searching && (
            <p className="text-sm text-muted-foreground">검색 결과 없음</p>
          )}
        </div>
      )}

      {/* 영상 그리드 */}
      {!query.trim() && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {loading && <p className="text-sm text-muted-foreground col-span-3">불러오는 중...</p>}
          {videos.map((v) => (
            <Link
              key={v.vid_id}
              href={`/slides/${v.vid_id}`}
              className="border rounded-xl overflow-hidden hover:shadow-md transition-shadow group"
            >
              {v.thumbnail ? (
                <img
                  src={`${API_BASE}/api/slides/${v.vid_id}/image/${v.thumbnail}`}
                  alt={v.title}
                  className="w-full h-40 object-cover bg-zinc-100 group-hover:scale-[1.02] transition-transform"
                />
              ) : (
                <div className="w-full h-40 bg-zinc-100 flex items-center justify-center">
                  <Images className="w-8 h-8 text-zinc-400" />
                </div>
              )}
              <div className="p-3 space-y-1">
                <p className="text-sm font-semibold line-clamp-2">{v.title}</p>
                <div className="flex items-center justify-between">
                  <Badge variant="secondary">{v.total_slides}장</Badge>
                  {v.url && (
                    <a
                      href={v.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      onClick={(e) => e.stopPropagation()}
                      className="text-muted-foreground hover:text-foreground"
                    >
                      <ExternalLink className="w-3.5 h-3.5" />
                    </a>
                  )}
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
