import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { isManagerRole, isTokenExpired, decodeTokenClaims, routeRequiresManager } from "@/lib/session";

const PUBLIC_PATHS = ["/login", "/auth/callback"];

/**
 * Edge gate: redirect to /login when there is no valid session cookie, and keep
 * non-managers out of manager screens. The cookie only mirrors the bearer token for
 * this purpose. The API verifies the token signature and enforces roles on every call.
 */
export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const token = request.cookies.get("orbit_token")?.value;
  const authed = Boolean(token) && !isTokenExpired(token);

  if (PUBLIC_PATHS.includes(pathname)) {
    // A signed-in user has no reason to see the login form.
    if (authed && pathname === "/login") return NextResponse.redirect(new URL("/", request.url));
    return NextResponse.next();
  }

  if (!authed) {
    const url = new URL("/login", request.url);
    if (token) url.searchParams.set("expired", "1");
    const response = NextResponse.redirect(url);
    if (token) response.cookies.delete("orbit_token");
    return response;
  }

  if (routeRequiresManager(pathname) && !isManagerRole(decodeTokenClaims(token)?.role)) {
    return NextResponse.redirect(new URL("/", request.url));
  }
  return NextResponse.next();
}

export const config = {
  // Everything except Next internals and static files.
  matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\\.(?:png|jpg|jpeg|svg|ico|webp|woff2?)$).*)"],
};
