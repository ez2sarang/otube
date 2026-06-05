import { NextRequest, NextResponse } from "next/server";

const API_BASE = process.env.INTERNAL_API_URL || "http://localhost:9102";

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ token: string }> }
) {
  const { token } = await params;
  const res = await fetch(`${API_BASE}/api/share/${token}`);
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
