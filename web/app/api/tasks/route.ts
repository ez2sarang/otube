import { NextRequest, NextResponse } from "next/server";

const API_BASE = process.env.INTERNAL_API_URL || "";

export async function POST(req: NextRequest) {
  if (!API_BASE) {
    return NextResponse.json({ error: "작업 생성 기능은 현재 준비 중입니다." }, { status: 503 });
  }
  const body = await req.json();
  const res = await fetch(`${API_BASE}/api/ai-tasks`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}

export async function GET() {
  if (!API_BASE) {
    return NextResponse.json([], { status: 200 });
  }
  const res = await fetch(`${API_BASE}/api/ai-tasks`, { cache: "no-store" });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
