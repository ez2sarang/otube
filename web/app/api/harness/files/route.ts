import { NextResponse } from "next/server";
import fs from "fs";
import path from "path";

const PROJECT_ROOT = path.resolve(process.cwd(), "..");
const HARNESS_DIR = path.join(PROJECT_ROOT, "harness");
const APP_HARNESS_DIR = path.join(PROJECT_ROOT, "app", "stt", "harness");

function walkMd(dir: string, base: string): string[] {
  const files: string[] = [];
  if (!fs.existsSync(dir)) return files;
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      files.push(...walkMd(full, base));
    } else if (entry.name.endsWith(".md")) {
      files.push(path.relative(base, full));
    }
  }
  return files;
}

function countFiles(dir: string, ext: string): number {
  if (!fs.existsSync(dir)) return 0;
  return fs.readdirSync(dir).filter((f) => f.endsWith(ext)).length;
}

export async function GET() {
  const files: string[] = [];

  for (const special of ["CLAUDE.md", "AGENTS.md"]) {
    if (fs.existsSync(path.join(PROJECT_ROOT, special))) {
      files.push(special);
    }
  }

  files.push(...walkMd(HARNESS_DIR, PROJECT_ROOT).sort());
  files.push(...walkMd(APP_HARNESS_DIR, PROJECT_ROOT).sort());

  const overview = {
    constitution: fs.existsSync(path.join(HARNESS_DIR, "core", "constitution.md")) ? "있음" : "없음",
    specs: `${countFiles(path.join(APP_HARNESS_DIR, "specs"), ".md")}개`,
    tests: `${countFiles(path.join(PROJECT_ROOT, "app", "stt", "tests"), ".py")}개`,
    workflows: `${countFiles(path.join(HARNESS_DIR, "workflows"), ".md")}개`,
  };

  return NextResponse.json({ files, overview });
}
