import { NextRequest, NextResponse } from "next/server";
import { createHmac } from "crypto";

const COOKIE_NAME = "otube_admin";

function verifyToken(token: string): boolean {
  try {
    const secret = process.env.NEXTAUTH_SECRET ?? "otube-secret-2026";
    const decoded = Buffer.from(token, "base64url").toString("utf-8");
    // format: email:timestamp|hmac
    const lastPipe = decoded.lastIndexOf("|");
    if (lastPipe === -1) return false;

    const payload = decoded.slice(0, lastPipe);
    const receivedHmac = decoded.slice(lastPipe + 1);

    const expectedHmac = createHmac("sha256", secret)
      .update(payload)
      .digest("hex");

    if (receivedHmac !== expectedHmac) return false;

    // payload is "email:timestamp" — check token not older than 7 days
    const colonIdx = payload.lastIndexOf(":");
    if (colonIdx === -1) return false;
    const timestamp = Number(payload.slice(colonIdx + 1));
    const age = Date.now() - timestamp;
    const maxAge = 7 * 24 * 60 * 60 * 1000;
    return age >= 0 && age <= maxAge;
  } catch {
    return false;
  }
}

export async function GET(req: NextRequest) {
  const token = req.cookies.get(COOKIE_NAME)?.value ?? "";
  const isAdmin = token.length > 0 && verifyToken(token);
  return NextResponse.json({ isAdmin });
}
