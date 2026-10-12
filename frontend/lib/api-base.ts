/**
 * Where the browser sends API calls.
 *
 * Normally that is the backend's own address (NEXT_PUBLIC_API_URL). On Vercel every deployment also has
 * its own address (orbit-abc123-team.vercel.app), and the backend only allows the addresses it knows, so
 * a browser on any other deployment is blocked and sign-in fails with "Cannot reach the server". On a
 * vercel.app address the dashboard therefore calls the backend through itself: the browser only talks to
 * the page's own address, which Next.js forwards to the backend (see next.config.mjs).
 */

export const PROXY_PREFIX = "/backend-api";
export const DEFAULT_API_URL = "http://localhost:8001/api";

export function isAbsolute(url: string): boolean {
  return /^https?:\/\//i.test(url);
}

export function resolveApiBase(configured: string | undefined, hostname?: string): string {
  const direct = configured || DEFAULT_API_URL;
  if (hostname && hostname.endsWith(".vercel.app") && isAbsolute(direct)) return PROXY_PREFIX;
  return direct;
}
