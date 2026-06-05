import { NextRequest, NextResponse } from "next/server";
import fs from "fs";
import path from "path";

const PROJECT_ROOT = path.resolve(process.cwd(), "..");

export async function POST(req: NextRequest) {
  const { name, category } = await req.json();
  if (!name) return NextResponse.json({ error: "파일 이름 필요" }, { status: 400 });

  const fileName = name.endsWith(".md") ? name : `${name}.md`;
  const relPath = (category || "harness/core/") + fileName;
  const full = path.join(PROJECT_ROOT, relPath);

  if (!full.startsWith(PROJECT_ROOT)) {
    return NextResponse.json({ error: "잘못된 경로" }, { status: 400 });
  }
  if (fs.existsSync(full)) {
    return NextResponse.json({ error: "이미 존재하는 파일" }, { status: 400 });
  }

  fs.mkdirSync(path.dirname(full), { recursive: true });
  const title = fileName.replace(".md", "").replace(/[-_]/g, " ");
  fs.writeFileSync(full, `# ${title}\n\n(내용을 작성해주세요)\n`, "utf-8");

  return NextResponse.json({ path: relPath, message: `생성 완료: ${relPath}` });
}
