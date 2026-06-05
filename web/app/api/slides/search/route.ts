import { NextRequest, NextResponse } from "next/server";

const SUPABASE_URL = process.env.SUPABASE_URL || "https://ydqypyddmugnzaovfdeo.supabase.co";
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY || "";
const SCHEMA = process.env.SUPABASE_SCHEMA || "stt_analysis";
const STORAGE_BUCKET = "slide-images";

export async function GET(req: NextRequest) {
  const q = req.nextUrl.searchParams.get("q") || "";
  if (!q.trim()) return NextResponse.json([]);

  const headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": `Bearer ${SUPABASE_KEY}`,
    "Accept-Profile": SCHEMA,
    "Range": "0-199",
    "Range-Unit": "items",
  };

  const [slidesRes, videosRes] = await Promise.all([
    fetch(
      `${SUPABASE_URL}/rest/v1/slides?select=video_id,slide_index,filename,time_str,ocr_text&ocr_text=ilike.*${encodeURIComponent(q)}*&order=video_id.asc,slide_index.asc`,
      { headers, cache: "no-store" }
    ),
    fetch(
      `${SUPABASE_URL}/rest/v1/videos?select=id,title`,
      { headers: { ...headers, "Range": "0-9999" }, cache: "no-store" }
    ),
  ]);

  if (!slidesRes.ok) return NextResponse.json([]);

  const slides: any[] = await slidesRes.json();
  const videos: any[] = videosRes.ok ? await videosRes.json() : [];
  const videoMap = new Map(videos.map((v: any) => [v.id, v.title]));
  const publicBase = `${SUPABASE_URL}/storage/v1/object/public/${STORAGE_BUCKET}`;

  const qLower = q.toLowerCase();
  const results = slides.map((s: any) => {
    const text = s.ocr_text || "";
    const idx = text.toLowerCase().indexOf(qLower);
    const start = Math.max(0, idx - 40);
    const end = Math.min(text.length, idx + q.length + 80);
    const excerpt = (start > 0 ? "..." : "") + text.slice(start, end) + (end < text.length ? "..." : "");
    return {
      vid_id: s.video_id,
      title: videoMap.get(s.video_id) || s.video_id,
      slide_index: s.slide_index,
      filename: s.filename,
      image_url: `${publicBase}/${s.video_id}/${s.filename}`,
      time_str: s.time_str,
      ocr_text: s.ocr_text,
      match_excerpt: excerpt,
    };
  });

  return NextResponse.json(results);
}
