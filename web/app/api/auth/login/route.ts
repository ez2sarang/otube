import { NextRequest, NextResponse } from "next/server";
import { createHmac, timingSafeEqual } from "crypto";

const COOKIE_NAME = "otube_admin";
const COOKIE_MAX_AGE = 7 * 24 * 60 * 60; // 7 days in seconds

function makeToken(email: string): string {
  const secret = process.env.NEXTAUTH_SECRET ?? "otube-secret-2026";
  const timestamp = Date.now().toString();
  const payload = `${email}:${timestamp}`;
  const hmac = createHmac("sha256", secret).update(payload).digest("hex");
  // encode as base64url: payload|hmac
  return Buffer.from(`${payload}|${hmac}`).toString("base64url");
}

function timingSafeCompare(a: string, b: string): boolean {
  const aBuf = Buffer.from(a);
  const bBuf = Buffer.from(b);
  if (aBuf.length !== bBuf.length) {
    // Still do a compare to avoid timing leakage on length
    timingSafeEqual(Buffer.alloc(aBuf.length), Buffer.alloc(aBuf.length));
    return false;
  }
  return timingSafeEqual(aBuf, bBuf);
}

export async function POST(req: NextRequest) {
  const adminEmail = process.env.ADMIN_EMAIL;
  const adminPassword = process.env.ADMIN_PASSWORD;

  if (!adminEmail || !adminPassword) {
    return NextResponse.json(
      { ok: false, error: "Server not configured" },
      { status: 500 }
    );
  }

  let body: { email?: string; password?: string };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ ok: false, error: "Invalid request" }, { status: 400 });
  }

  const { email = "", password = "" } = body;

  const emailMatch = timingSafeCompare(email, adminEmail);
  const passwordMatch = timingSafeCompare(password, adminPassword);

  if (!emailMatch || !passwordMatch) {
    return NextResponse.json({ ok: false, error: "Invalid credentials" }, { status: 401 });
  }

  const token = makeToken(email);

  const res = NextResponse.json({ ok: true });
  res.cookies.set(COOKIE_NAME, token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    maxAge: COOKIE_MAX_AGE,
    path: "/",
  });

  return res;
}
