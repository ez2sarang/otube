import { NextResponse } from "next/server";

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

async function sbGetAll(table: string, qs: string = ""): Promise<any[]> {
  const PAGE = 1000;
  const results: any[] = [];
  let offset = 0;
  while (true) {
    const params = [qs, `limit=${PAGE}`, `offset=${offset}`].filter(Boolean).join("&");
    const url = `${SUPABASE_URL}/rest/v1/${table}?${params}`;
    const res = await fetch(url, { headers: sbHeaders(), cache: "no-store" });
    if (!res.ok) break;
    const page: any[] = await res.json();
    results.push(...page);
    if (page.length < PAGE) break;
    offset += PAGE;
  }
  return results;
}

export async function GET() {
  const allSlides = await sbGetAll(
    "slides",
    "select=video_id,slide_index,filename,extracted_at&order=video_id.asc,slide_index.asc"
  );

  // slides에 등장하는 video_id로만 영상 정보 조회
  const videoIds = [...new Set(allSlides.map((s: any) => s.video_id))];
  let videos: any[] = [];
  if (videoIds.length > 0) {
    const idFilter = videoIds.map(id => encodeURIComponent(id)).join(",");
    videos = await sbGetAll("videos", `select=id,title,url,thumbnail&id=in.(${idFilter})`);
  }

  const videoMap = new Map(videos.map((v: any) => [v.id, v]));
  const publicBase = `${SUPABASE_URL}/storage/v1/object/public/${STORAGE_BUCKET}`;

  // video_id별 집계
  const groupMap = new Map<string, { total: number; first_filename: string; extracted_at: string }>();
  for (const s of allSlides) {
    if (!groupMap.has(s.video_id)) {
      groupMap.set(s.video_id, { total: 1, first_filename: s.filename, extracted_at: s.extracted_at });
    } else {
      groupMap.get(s.video_id)!.total++;
    }
  }

  const result = Array.from(groupMap.entries())
    .map(([vid_id, g]) => {
      const video = videoMap.get(vid_id);
      return {
        vid_id,
        title: video?.title || vid_id,
        url: video?.url || "",
        total_slides: g.total,
        extracted_at: g.extracted_at,
        thumbnail: video?.thumbnail || `${publicBase}/${vid_id}/${g.first_filename}`,
      };
    })
    .sort((a, b) => b.total_slides - a.total_slides);

  return NextResponse.json(result);
}
