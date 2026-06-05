import { NextRequest, NextResponse } from "next/server";

const API_BASE = process.env.INTERNAL_API_URL || "http://localhost:9102";

async function safeJson(res: Response, fallback: unknown = null) {
  if (!res.ok) return fallback;
  try { return await res.json(); } catch { return fallback; }
}

export async function GET(req: NextRequest) {
  const id = req.nextUrl.searchParams.get("id");
  const channel = req.nextUrl.searchParams.get("channel");
  const collectionId = req.nextUrl.searchParams.get("collection");
  const search = req.nextUrl.searchParams.get("search");

  try {
    // 단일 영상 상세
    if (id) {
      const [transcriptRes, summaryRes, collectionsRes] = await Promise.all([
        fetch(`${API_BASE}/api/videos/${id}/transcript`),
        fetch(`${API_BASE}/api/videos/summary`),
        fetch(`${API_BASE}/api/collections`),
      ]);

      const [transcript, summary, collections] = await Promise.all([
        safeJson(transcriptRes, {}),
        safeJson(summaryRes, null),
        safeJson(collectionsRes, []),
      ]);

      const videosRes = await fetch(`${API_BASE}/api/videos`);
      const items = await safeJson(videosRes, []);
      const item = Array.isArray(items) ? items.find((i: any) => i.id === id) : null;
      if (!item) return NextResponse.json({ error: "Not found" }, { status: 404 });

      return NextResponse.json({
        ...item,
        fullText: (transcript as any).fullText || "",
        segments: (transcript as any).segments || [],
      });
    }

    // 목록 + 요약
    const params = new URLSearchParams();
    if (channel) params.set("channel", channel);
    if (collectionId) params.set("collection_id", collectionId);
    if (search) params.set("search", search);

    const [itemsRes, summaryRes, collectionsRes, pendingRes] = await Promise.all([
      fetch(`${API_BASE}/api/videos?${params}`),
      fetch(`${API_BASE}/api/videos/summary`),
      fetch(`${API_BASE}/api/collections`),
      fetch(`${API_BASE}/api/slides-unprocessed`),
    ]);

    const [items, summary, collections, pending] = await Promise.all([
      safeJson(itemsRes, []),
      safeJson(summaryRes, null),
      safeJson(collectionsRes, []),
      safeJson(pendingRes, []),
    ]);

    const processedItems = Array.isArray(items) ? items : [];
    const pendingItems = Array.isArray(pending) ? pending : [];

    return NextResponse.json({
      items: [...processedItems, ...pendingItems],
      collections: Array.isArray(collections) ? collections : [],
      summary,
    });
  } catch (err) {
    console.error("[api/history] upstream error:", err);
    return NextResponse.json({ items: [], collections: [], summary: null }, { status: 200 });
  }
}
