import { NextRequest, NextResponse } from "next/server";

const API_BASE = process.env.INTERNAL_API_URL || "";

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ token: string }> }
) {
  if (!API_BASE) {
    return NextResponse.json({ error: "공유 기능은 현재 준비 중입니다." }, { status: 503 });
  }
  const { token } = await params;
  const res = await fetch(`${API_BASE}/api/share/${token}`);
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
