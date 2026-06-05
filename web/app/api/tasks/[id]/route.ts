import { NextRequest, NextResponse } from "next/server";

const API_BASE = process.env.INTERNAL_API_URL || "";

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  if (!API_BASE) return NextResponse.json({ error: "Not available" }, { status: 503 });
  const { id } = await params;
  const res = await fetch(`${API_BASE}/api/ai-tasks/${id}`, { cache: "no-store" });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}

export async function PATCH(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  if (!API_BASE) return NextResponse.json({ error: "Not available" }, { status: 503 });
  const { id } = await params;
  const body = await req.json();
  const res = await fetch(`${API_BASE}/api/ai-tasks/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
