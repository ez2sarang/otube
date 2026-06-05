import { NextRequest, NextResponse } from "next/server";

const SUPABASE_URL = process.env.SUPABASE_URL || "https://ydqypyddmugnzaovfdeo.supabase.co";
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY || "";
const SCHEMA = process.env.SUPABASE_SCHEMA || "stt_analysis";

function sbHeaders() {
  return {
    "apikey": SUPABASE_KEY,
    "Authorization": `Bearer ${SUPABASE_KEY}`,
    "Accept-Profile": SCHEMA,
  };
}

async function sbGet(table: string, qs: string = "", rangeEnd = 9999) {
  const url = `${SUPABASE_URL}/rest/v1/${table}${qs ? `?${qs}` : ""}`;
  const res = await fetch(url, {
    headers: { ...sbHeaders(), "Range-Unit": "items", "Range": `0-${rangeEnd}` },
    cache: "no-store",
  });
  if (!res.ok) return null;
  return res.json();
}

export async function GET(req: NextRequest) {
  const id = req.nextUrl.searchParams.get("id");
  const channel = req.nextUrl.searchParams.get("channel");
  const collectionId = req.nextUrl.searchParams.get("collection");
  const search = req.nextUrl.searchParams.get("search");

  try {
    // 단일 영상 상세
    if (id) {
      const [videoArr, transcriptArr] = await Promise.all([
        sbGet("videos", `id=eq.${encodeURIComponent(id)}&limit=1`),
        sbGet("transcripts", `video_id=eq.${encodeURIComponent(id)}&limit=1`),
      ]);
      const item = Array.isArray(videoArr) && videoArr[0] ? videoArr[0] : null;
      if (!item) return NextResponse.json({ error: "Not found" }, { status: 404 });
      const transcript = Array.isArray(transcriptArr) && transcriptArr[0] ? transcriptArr[0] : {};
      return NextResponse.json({
        id: item.id,
        title: item.title,
        channel: item.channel,
        url: item.url,
        duration_sec: item.duration_sec,
        text_length: item.text_length,
        segment_count: item.segment_count,
        language: item.language,
        processed_at: item.processed_at,
        thumbnail: item.thumbnail,
        fullText: transcript.corrected_text || transcript.full_text || "",
        segments: transcript.segments || [],
      });
    }

    // 필터 조건 조립
    const conditions: string[] = [];
    if (channel) conditions.push(`channel=eq.${encodeURIComponent(channel)}`);
    if (collectionId) conditions.push(`collection_id=eq.${encodeURIComponent(collectionId)}`);
    if (search) conditions.push(`title=ilike.*${encodeURIComponent(search)}*`);
    const qs = [...conditions, "order=processed_at.desc", "limit=2000"].join("&");

    const [videos, collections] = await Promise.all([
      sbGet("videos", qs),
      sbGet("collections", "order=created_at.desc"),
    ]);

    const items = Array.isArray(videos) ? videos : [];

    // 요약 계산
    const channels: Record<string, { count: number; totalDuration: number; totalChars: number }> = {};
    let totalDuration = 0, totalChars = 0;
    for (const v of items) {
      const ch = v.channel || "unknown";
      if (!channels[ch]) channels[ch] = { count: 0, totalDuration: 0, totalChars: 0 };
      channels[ch].count++;
      channels[ch].totalDuration += v.duration_sec || 0;
      channels[ch].totalChars += v.text_length || 0;
      totalDuration += v.duration_sec || 0;
      totalChars += v.text_length || 0;
    }
    const summary = { total: items.length, channels, totalDuration, totalChars };

    const mappedItems = items.map((v: any) => ({
      id: v.id,
      title: v.title,
      channel: v.channel,
      url: v.url,
      duration_sec: v.duration_sec || 0,
      text_length: v.text_length || 0,
      segments: v.segment_count || 0,
      language: v.language,
      processed_at: v.processed_at,
      preview: v.preview || "",
      thumbnail: v.thumbnail,
      slide_count: v.slides_count || 0,
    }));

    return NextResponse.json({
      items: mappedItems,
      collections: Array.isArray(collections) ? collections : [],
      summary,
    });
  } catch (err) {
    console.error("[api/history] error:", err);
    return NextResponse.json({ items: [], collections: [], summary: null }, { status: 200 });
  }
}
