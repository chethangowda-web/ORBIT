import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { buildCsp, generateNonce } from "@/lib/csp";
import { isManagerRole, isTokenExpired, decodeTokenClaims, routeRequiresManager } from "@/lib/session";

const PUBLIC_PATHS = ["/login"];
const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001/api";

/** Attach the per-request CSP to a response (and forward the nonce so Next tags its scripts). */
function withCsp(request: NextRequest, build: (headers: Headers) => NextResponse): NextResponse {
  const nonce = generateNonce();
  const csp = buildCsp({ nonce, apiUrl: API_URL, isDev: process.env.NODE_ENV !== "production" });
  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-nonce", nonce);
  requestHeaders.set("content-security-policy", csp);
  const response = build(requestHeaders);
  response.headers.set("content-security-policy", csp);
  return response;
}

const proceed = (request: NextRequest) =>
  withCsp(request, (headers) => NextResponse.next({ request: { headers } }));

const redirect = (request: NextRequest, url: URL) => withCsp(request, () => NextResponse.redirect(url));

/**
 * Edge gate: redirect to /login when there is no valid session cookie, and keep
 * non-managers out of manager screens. The cookie only mirrors the bearer token for
 * this purpose. The API verifies the token signature and enforces roles on every call.
 * Every response also carries a nonce-based Content-Security-Policy.
 */
export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const token = request.cookies.get("orbit_token")?.value;
  const authed = Boolean(token) && !isTokenExpired(token);

  if (PUBLIC_PATHS.includes(pathname)) {
    // A signed-in user has no reason to see the login form.
    if (authed && pathname === "/login") return redirect(request, new URL("/", request.url));
    return proceed(request);
  }

  if (!authed) {
    const url = new URL("/login", request.url);
    if (token) url.searchParams.set("expired", "1");
    const response = redirect(request, url);
    if (token) response.cookies.delete("orbit_token");
    return response;
  }

  if (routeRequiresManager(pathname) && !isManagerRole(decodeTokenClaims(token)?.role)) {
    return redirect(request, new URL("/", request.url));
  }
  return proceed(request);
}

export const config = {
  // Everything except Next internals, static files and the backend proxy (the API checks its own tokens).
  matcher: ["/((?!_next/static|_next/image|backend-api/|favicon.ico|.*\\.(?:png|jpg|jpeg|svg|ico|webp|woff2?)$).*)"],
};
