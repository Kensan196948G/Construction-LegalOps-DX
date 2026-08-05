import { NextResponse } from "next/server";

/**
 * Liveness probe for the Next.js standalone server.
 *
 * `middleware.ts` excludes `/api/*` from the NextAuth/Cloudflare Access
 * redirect, so this endpoint returns 200 without issuing a 307. Container
 * healthchecks MUST target this path (or another auth-exempt 200 route):
 * probing `/` follows the middleware redirect to the Cloudflare Access login
 * over TLS, which leaves orphaned `ssl_client` children behind (zombies) when
 * the probe is timed out.
 */
export const dynamic = "force-dynamic";

export function GET() {
  return NextResponse.json({ status: "ok", service: "frontend" });
}
