import { NextRequest, NextResponse } from "next/server";

const API_BASE = process.env.INTERNAL_API_URL || "http://localhost:9102";

export async function POST(req: NextRequest) {
  const { video_id } = await req.json();
  if (!video_id) {
    return NextResponse.json({ error: "video_id required" }, { status: 400 });
  }
  const res = await fetch(`${API_BASE}/api/videos/${video_id}/share`, {
    method: "POST",
  });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
