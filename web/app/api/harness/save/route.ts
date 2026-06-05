import { NextRequest, NextResponse } from "next/server";
import fs from "fs";
import path from "path";

const PROJECT_ROOT = path.resolve(process.cwd(), "..");

export async function POST(req: NextRequest) {
  const { path: filePath, content } = await req.json();
  if (!filePath) return NextResponse.json({ error: "경로 필요" }, { status: 400 });

  const full = path.join(PROJECT_ROOT, filePath);
  if (!full.startsWith(PROJECT_ROOT)) {
    return NextResponse.json({ error: "잘못된 경로" }, { status: 400 });
  }

  fs.mkdirSync(path.dirname(full), { recursive: true });
  fs.writeFileSync(full, content, "utf-8");

  return NextResponse.json({ message: `저장 완료: ${filePath} (${content.length}자)` });
}
