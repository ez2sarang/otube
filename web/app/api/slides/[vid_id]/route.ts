import { NextRequest, NextResponse } from "next/server";

const SUPABASE_URL = process.env.SUPABASE_URL || "https://ydqypyddmugnzaovfdeo.supabase.co";
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY || "";
const SCHEMA = process.env.SUPABASE_SCHEMA || "stt_analysis";
const STORAGE_BUCKET = "slide-images";

function sbHeaders() {
  return {
    "apikey": SUPABASE_KEY,
    "Authorization": `Bearer ${SUPABASE_KEY}`,
    "Accept-Profile": SCHEMA,
  };
}

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ vid_id: string }> }
) {
  const { vid_id } = await params;

  const [videoRes, slidesRes] = await Promise.all([
    fetch(
      `${SUPABASE_URL}/rest/v1/videos?id=eq.${encodeURIComponent(vid_id)}&limit=1`,
      { headers: sbHeaders(), cache: "no-store" }
    ),
    fetch(
      `${SUPABASE_URL}/rest/v1/slides?video_id=eq.${encodeURIComponent(vid_id)}&select=slide_index,filename,frame_time,time_str,ocr_text,llm_summary&order=slide_index.asc`,
      {
        headers: { ...sbHeaders(), "Range": "0-9999", "Range-Unit": "items" },
        cache: "no-store",
      }
    ),
  ]);

  if (!videoRes.ok || !slidesRes.ok) {
    return NextResponse.json({ error: "Not found" }, { status: 404 });
  }

  const videos = await videoRes.json();
  const slides = await slidesRes.json();

  const video = Array.isArray(videos) && videos[0] ? videos[0] : null;
  if (!video) return NextResponse.json({ error: "Video not found" }, { status: 404 });

  const publicBase = `${SUPABASE_URL}/storage/v1/object/public/${STORAGE_BUCKET}/${vid_id}`;

  const mappedSlides = (Array.isArray(slides) ? slides : []).map((s: any) => ({
    slide_index: s.slide_index,
    timestamp: s.frame_time || 0,
    time_str: s.time_str || "",
    filename: s.filename,
    image_url: `${publicBase}/${s.filename}`,
    ocr_text: s.ocr_text || "",
    llm_summary: s.llm_summary || "",
  }));

  return NextResponse.json({
    video_id: vid_id,
    title: video.title,
    url: video.url,
    total_slides: mappedSlides.length,
    extracted_at: video.processed_at,
    slides: mappedSlides,
  });
}
