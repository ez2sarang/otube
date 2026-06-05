import { NextRequest } from "next/server";

const API_BASE = process.env.INTERNAL_API_URL || "http://localhost:9102";

export async function POST(req: NextRequest) {
  const body = await req.json();
  const { video_id, video_ids, question, history = [] } = body;

  // 다중 영상 요청
  if (video_ids && Array.isArray(video_ids) && video_ids.length > 0) {
    const upstream = await fetch(`${API_BASE}/api/videos/ask-multi`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ video_ids, question, history }),
    });
    if (!upstream.ok) {
      return new Response(JSON.stringify({ error: "API 오류" }), { status: 500 });
    }
    return new Response(upstream.body, {
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
      },
    });
  }

  // 단건 요청 (기존)
  const upstream = await fetch(`${API_BASE}/api/videos/${video_id}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, history }),
  });

  if (!upstream.ok) {
    return new Response(JSON.stringify({ error: "API 오류" }), { status: 500 });
  }

  return new Response(upstream.body, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      "X-Accel-Buffering": "no",
    },
  });
}
