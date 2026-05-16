import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

/**
 * 認証ミドルウェア — 一時無効化中
 *
 * 再有効化するには:
 *   cp middleware.ts.auth-disabled-backup middleware.ts
 * の後にサービスを再起動してください。
 */
export function middleware(_request: NextRequest): NextResponse {
  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"],
};
