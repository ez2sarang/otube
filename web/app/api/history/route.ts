import { NextRequest, NextResponse } from "next/server";

const API_BASE = process.env.INTERNAL_API_URL || "http://localhost:9102";

export async function GET(req: NextRequest) {
  const id = req.nextUrl.searchParams.get("id");
  const channel = req.nextUrl.searchParams.get("channel");
  const collectionId = req.nextUrl.searchParams.get("collection");
  const search = req.nextUrl.searchParams.get("search");

  try {
    // 단일 영상 상세
    if (id) {
      const [videoRes, transcriptRes] = await Promise.all([
        fetch(`${API_BASE}/api/videos/${encodeURIComponent(id)}`, { cache: "no-store" }),
        fetch(`${API_BASE}/api/videos/${encodeURIComponent(id)}/transcript`, { cache: "no-store" }),
      ]);
      if (!videoRes.ok) return NextResponse.json({ error: "Not found" }, { status: 404 });
      const item = await videoRes.json();
      const transcript = transcriptRes.ok ? await transcriptRes.json() : {};
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
        fullText: transcript.correctedText || transcript.fullText || "",
        segments: transcript.segments || [],
      });
    }

    // 쿼리 파라미터 조립
    const params = new URLSearchParams();
    if (channel) params.set("channel", channel);
    if (collectionId) params.set("collection_id", collectionId);
    if (search) params.set("search", search);
    const qs = params.toString();

    const [videosRes, summaryRes, collectionsRes] = await Promise.all([
      fetch(`${API_BASE}/api/videos${qs ? `?${qs}` : ""}`, { cache: "no-store" }),
      fetch(`${API_BASE}/api/videos/summary`, { cache: "no-store" }),
      fetch(`${API_BASE}/api/collections`, { cache: "no-store" }),
    ]);

    const videos = videosRes.ok ? await videosRes.json() : [];
    const summaryRaw = summaryRes.ok ? await summaryRes.json() : null;
    const collections = collectionsRes.ok ? await collectionsRes.json() : [];

    const items = Array.isArray(videos) ? videos : [];

    const summary = summaryRaw ? {
      total: summaryRaw.total || 0,
      channels: summaryRaw.channels || {},
      totalDuration: summaryRaw.totalDuration || 0,
      totalChars: summaryRaw.totalChars || 0,
    } : null;

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
