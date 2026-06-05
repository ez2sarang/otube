import { NextResponse } from "next/server";

const SUPABASE_URL = process.env.SUPABASE_URL || "https://ydqypyddmugnzaovfdeo.supabase.co";
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY || "";
const SCHEMA = process.env.SUPABASE_SCHEMA || "stt_analysis";
const STORAGE_BUCKET = "slide-images";

export async function GET() {
  const headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": `Bearer ${SUPABASE_KEY}`,
    "Accept-Profile": SCHEMA,
    "Range": "0-9999",
    "Range-Unit": "items",
  };

  // slides 테이블에서 video_id별 집계
  const [slidesRes, videosRes] = await Promise.all([
    fetch(
      `${SUPABASE_URL}/rest/v1/slides?select=video_id,slide_index,filename,extracted_at&order=video_id.asc`,
      { headers, cache: "no-store" }
    ),
    fetch(
      `${SUPABASE_URL}/rest/v1/videos?select=id,title,url,thumbnail&slides_count=gt.0`,
      { headers, cache: "no-store" }
    ),
  ]);

  if (!slidesRes.ok || !videosRes.ok) {
    return NextResponse.json([], { status: 200 });
  }

  const slides: any[] = await slidesRes.json();
  const videos: any[] = await videosRes.json();

  const videoMap = new Map(videos.map((v: any) => [v.id, v]));

  // video_id별 집계
  const groupMap = new Map<string, { total: number; thumbnail_filename: string; extracted_at: string }>();
  for (const s of slides) {
    const g = groupMap.get(s.video_id) || { total: 0, thumbnail_filename: s.filename, extracted_at: s.extracted_at };
    g.total++;
    if (s.slide_index === 0) g.thumbnail_filename = s.filename;
    if (!groupMap.has(s.video_id)) groupMap.set(s.video_id, g);
    else groupMap.get(s.video_id)!.total++;
  }

  const publicBase = `${SUPABASE_URL}/storage/v1/object/public/${STORAGE_BUCKET}`;

  const result = Array.from(groupMap.entries())
    .map(([vid_id, g]) => {
      const video = videoMap.get(vid_id);
      return {
        vid_id,
        title: video?.title || vid_id,
        url: video?.url || "",
        total_slides: g.total,
        extracted_at: g.extracted_at,
        thumbnail: video?.thumbnail || `${publicBase}/${vid_id}/${g.thumbnail_filename}`,
      };
    })
    .sort((a, b) => b.total_slides - a.total_slides);

  return NextResponse.json(result);
}
