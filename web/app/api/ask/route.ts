import { NextRequest, NextResponse } from "next/server";

const API_BASE = process.env.INTERNAL_API_URL || "";

export async function POST(req: NextRequest) {
  // Q&A는 내부 LLM 게이트웨이 필요 — 클라우드 배포 시 아직 미지원
  if (!API_BASE) {
    return NextResponse.json(
      { error: "Q&A 기능은 현재 준비 중입니다." },
      { status: 503 }
    );
  }

  const body = await req.json();
  const { video_id, video_ids, question, history = [] } = body;

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
