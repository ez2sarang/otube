import { NextRequest, NextResponse } from "next/server";
import fs from "fs";
import path from "path";

const PROJECT_ROOT = path.resolve(process.cwd(), "..");

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ videoId: string; index: string }> }
) {
  const { videoId, index } = await params;
  const idx = parseInt(index, 10);
  const framePath = path.join(PROJECT_ROOT, "data", "clips", videoId, `frame_${String(idx).padStart(4, "0")}.jpg`);

  if (!fs.existsSync(framePath)) {
    return NextResponse.json({ error: "Not found" }, { status: 404 });
  }

  const file = fs.readFileSync(framePath);
  return new NextResponse(file, {
    headers: {
      "Content-Type": "image/jpeg",
      "Cache-Control": "public, max-age=86400",
    },
  });
}
