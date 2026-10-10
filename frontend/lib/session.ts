/**
 * Pure session helpers shared by the auth provider and the edge middleware.
 *
 * The JWT payload is decoded WITHOUT verifying the signature. That is fine for UX
 * decisions (is the token expired? which role to show?) because the backend verifies
 * the signature and enforces authorization on every request.
 */

import type { UserRole } from "@/types";

export interface TokenClaims {
  sub?: string;
  email?: string;
  role?: UserRole;
  exp?: number;
}

export function decodeTokenClaims(token: string | undefined | null): TokenClaims | null {
  if (!token) return null;
  const parts = token.split(".");
  if (parts.length !== 3) return null;
  try {
    const base64 = parts[1].replace(/-/g, "+").replace(/_/g, "/");
    const padded = base64 + "=".repeat((4 - (base64.length % 4)) % 4);
    const json = atob(padded);
    const claims = JSON.parse(decodeURIComponent(escape(json))) as TokenClaims;
    return typeof claims === "object" && claims !== null ? claims : null;
  } catch {
    return null;
  }
}

/** True when the token is missing, malformed or past its `exp` (with a small skew). */
export function isTokenExpired(token: string | undefined | null, nowSeconds = Date.now() / 1000): boolean {
  const claims = decodeTokenClaims(token);
  if (!claims?.exp) return true;
  return claims.exp <= nowSeconds + 5;
}

export type RoleCheck = (role: UserRole | undefined | null) => boolean;

export const isManagerRole: RoleCheck = (role) => role === "manager" || role === "admin";
export const isAdminRole: RoleCheck = (role) => role === "admin";

/** Routes that require manager or admin. Backend enforces the same; this avoids dead ends. */
export const MANAGER_ROUTES = ["/insights", "/admin"];

export function routeRequiresManager(pathname: string): boolean {
  return MANAGER_ROUTES.some((route) => pathname === route || pathname.startsWith(`${route}/`));
}
