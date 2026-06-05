import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { ExternalLink, Clock, FileText, User, Layers, AlignLeft } from "lucide-react";
import { ShareCopyButton, ShareUrlBar } from "@/components/ShareCopyButton";
import { headers } from "next/headers";

const API_BASE = process.env.INTERNAL_API_URL || "http://localhost:9102";

function fmtDur(sec: number) {
  const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60);
  return h > 0 ? `${h}시간 ${m}분` : `${m}분`;
}

async function fetchShareData(token: string) {
  const res = await fetch(`${API_BASE}/api/share/${token}`, { cache: "no-store" });
  if (!res.ok) return null;
  const data = await res.json();
  if (data.error) return null;
  return data;
}


export async function generateMetadata(
  { params }: { params: Promise<{ token: string }> }
): Promise<Metadata> {
  const { token } = await params;
  const data = await fetchShareData(token);
  if (!data) return { title: "Offline Thinking — 공유 영상" };

  const { video, transcript } = data;
  const description = (video.preview || transcript || "")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 155);
  const thumbnail = video.thumbnail || `https://img.youtube.com/vi/${video.id}/maxresdefault.jpg`;

  return {
    title: `${video.title} — Offline Thinking`,
    description,
    openGraph: {
      type: "article",
      title: video.title,
      description,
      images: [{ url: thumbnail, width: 1280, height: 720, alt: video.title }],
      siteName: "Offline Thinking",
    },
    twitter: {
      card: "summary_large_image",
      title: video.title,
      description,
      images: [thumbnail],
    },
    other: {
      "llm:content-type": "video-transcript",
      "llm:language": video.language || "ko",
      "llm:channel": video.channel || "",
      "llm:duration": String(video.duration_sec || 0),
    },
  };
}

export default async function SharePage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;

  const data = await fetchShareData(token);
  if (!data) notFound();

  const { video, transcript, segments } = data;
  const headersList = await headers();
  const host = headersList.get("host") || "localhost:3204";
  const proto = process.env.NODE_ENV === "production" ? "https" : "http";
  const shareUrl = `${proto}://${host}/share/${token}`;

  const hasSegments = Array.isArray(segments) && segments.length > 0;

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "VideoObject",
    "name": video.title,
    "description": video.preview || (typeof transcript === "string" ? transcript.slice(0, 300) : ""),
    "thumbnailUrl": video.thumbnail || `https://img.youtube.com/vi/${video.id}/maxresdefault.jpg`,
    "uploadDate": video.upload_date || undefined,
    "duration": video.duration_sec > 0 ? `PT${video.duration_sec}S` : undefined,
    "url": video.url,
    "inLanguage": video.language || "ko",
    "author": video.channel ? { "@type": "Person", "name": video.channel } : undefined,
    "transcript": typeof transcript === "string" ? transcript.slice(0, 5000) : undefined,
  };

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
    <div className="max-w-3xl mx-auto px-4 py-8 space-y-6">
      {/* 공유 URL 바 */}
      <ShareUrlBar url={shareUrl} />

      {/* 영상 헤더 */}
      <div className="space-y-4">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={video.thumbnail || `https://img.youtube.com/vi/${video.id}/maxresdefault.jpg`}
          alt={video.title}
          className="w-full aspect-video object-cover rounded-xl shadow-lg"
        />
        <div>
          <h1 className="text-xl font-bold leading-snug">{video.title}</h1>
          <div className="flex flex-wrap items-center gap-2 mt-2">
            <Badge variant="outline" className="gap-1">
              <User className="w-3 h-3" />{video.channel}
            </Badge>
            {video.duration_sec > 0 && (
              <Badge variant="outline" className="gap-1">
                <Clock className="w-3 h-3" />{fmtDur(video.duration_sec)}
              </Badge>
            )}
            <Badge variant="outline" className="gap-1">
              <FileText className="w-3 h-3" />{(video.text_length / 1000).toFixed(1)}K자
            </Badge>
            {hasSegments && (
              <Badge variant="outline" className="gap-1">
                <Layers className="w-3 h-3" />{segments.length}개 세그먼트
              </Badge>
            )}
            {video.upload_date && (
              <span className="text-xs text-muted-foreground">{video.upload_date}</span>
            )}
          </div>
        </div>

        <div className="flex gap-2 flex-wrap">
          <a href={video.url} target="_blank" rel="noopener noreferrer">
            <Button variant="outline" size="sm" className="gap-1.5">
              <ExternalLink className="w-3.5 h-3.5" />YouTube에서 보기
            </Button>
          </a>
          <ShareCopyButton url={shareUrl} />
        </div>
      </div>

      <Separator />

      {/* 타임라인 세그먼트 */}
      {hasSegments ? (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <Clock className="w-4 h-4 text-primary" />
              타임라인
              <Badge variant="secondary" className="text-[10px]">{segments.length}개</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="max-h-[60vh] overflow-y-auto space-y-0.5 border rounded-lg p-2 bg-muted/20">
              {segments.map((seg: { time_str: string; text: string }, i: number) => (
                <div key={i} className="flex gap-3 py-1.5 px-2 hover:bg-muted/50 rounded-md group">
                  <a
                    href={`${video.url}&t=${Math.floor(seg.time_str.split(":").reduce((acc: number, v: string) => acc * 60 + parseInt(v), 0))}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-[11px] font-mono text-primary font-semibold shrink-0 pt-0.5 w-14 hover:underline"
                  >
                    {seg.time_str}
                  </a>
                  <span className="text-[12px] text-foreground leading-relaxed">{seg.text}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      ) : transcript ? (
        /* 세그먼트 없으면 전체 텍스트 */
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <AlignLeft className="w-4 h-4 text-primary" />
              트랜스크립트
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="whitespace-pre-wrap text-sm leading-relaxed text-foreground/90 font-mono bg-muted/30 rounded-lg p-4 max-h-[60vh] overflow-y-auto">
              {transcript}
            </div>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="py-8 text-center">
            <p className="text-sm text-muted-foreground">트랜스크립트가 없습니다.</p>
          </CardContent>
        </Card>
      )}

      {/* 전체 텍스트 (세그먼트가 있을 때는 접어서 보여줌) */}
      {hasSegments && transcript && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <AlignLeft className="w-4 h-4 text-primary" />
              전체 텍스트
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="whitespace-pre-wrap text-sm leading-relaxed text-foreground/90 bg-muted/30 rounded-lg p-4 max-h-[40vh] overflow-y-auto">
              {transcript}
            </div>
          </CardContent>
        </Card>
      )}

      {/* 푸터 */}
      <div className="text-center pt-4 border-t">
        <p className="text-xs text-muted-foreground">
          Offline Thinking으로 분석된 영상입니다.
        </p>
      </div>
    </div>
    </>
  );
}
