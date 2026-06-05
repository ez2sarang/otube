import { NextRequest } from "next/server";

const API_BASE = process.env.INTERNAL_API_URL || "";

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  if (!API_BASE) return new Response("Not available", { status: 503 });
  const { id } = await params;
  const res = await fetch(`${API_BASE}/api/ai-tasks/${id}/download`);
  if (!res.ok) return new Response("Not found", { status: 404 });
  const content = await res.arrayBuffer();
  return new Response(content, {
    headers: {
      "Content-Type": res.headers.get("content-type") || "text/plain",
      "Content-Disposition": res.headers.get("content-disposition") || `attachment; filename="task.txt"`,
    },
  });
}
