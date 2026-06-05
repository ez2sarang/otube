import { NextRequest, NextResponse } from "next/server";
import fs from "fs";
import path from "path";

const PROJECT_ROOT = path.resolve(process.cwd(), "..");

export async function GET(req: NextRequest) {
  const filePath = req.nextUrl.searchParams.get("path") || "";
  const full = path.join(PROJECT_ROOT, filePath);

  if (!full.startsWith(PROJECT_ROOT) || !fs.existsSync(full)) {
    return NextResponse.json({ content: "", info: `파일 없음: ${filePath}` });
  }

  const content = fs.readFileSync(full, "utf-8");
  const lines = content.split("\n").length;

  let cat = "기타";
  if (filePath.includes("core/")) cat = "레포 하네스 > 코어";
  else if (filePath.includes("roles/")) cat = "레포 하네스 > 역할";
  else if (filePath.includes("workflows/")) cat = "레포 하네스 > 워크플로우";
  else if (filePath.includes("specs/")) cat = "앱 하네스 > 기능 명세";
  else if (filePath.includes("docs/")) cat = "앱 하네스 > 문서";
  else if (filePath.includes("plans/")) cat = "앱 하네스 > 로드맵";
  else if (filePath.includes("references/")) cat = "앱 하네스 > 참고 자료";
  else if (filePath === "AGENTS.md" || filePath === "CLAUDE.md") cat = "루트";

  return NextResponse.json({
    content,
    info: `${cat} | ${filePath} | ${content.length}자, ${lines}줄`,
  });
}
