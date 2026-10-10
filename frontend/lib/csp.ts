/**
 * Content-Security-Policy builder. Pure so it can be unit-tested and reused by the edge
 * middleware, which supplies a fresh nonce per request.
 *
 * Scripts: only same-origin files and scripts carrying the request nonce (`strict-dynamic`
 * lets those load their own chunks), so injected markup cannot run script.
 * Styles keep 'unsafe-inline' because React sets style attributes (chart and progress widths);
 * that does not permit script execution.
 */

export interface CspOptions {
  nonce: string;
  /** Browser-visible API base, e.g. http://localhost:8001/api; its origin is allowed for fetch. */
  apiUrl: string;
  /** Dev server needs eval for hot reload; never enabled in production. */
  isDev?: boolean;
}

export function originOf(url: string): string | null {
  try {
    return new URL(url).origin;
  } catch {
    return null;
  }
}

export function buildCsp({ nonce, apiUrl, isDev = false }: CspOptions): string {
  const apiOrigin = originOf(apiUrl);
  const connect = ["'self'", ...(apiOrigin ? [apiOrigin] : []), ...(isDev ? ["ws:", "wss:"] : [])];
  const scripts = ["'self'", `'nonce-${nonce}'`, "'strict-dynamic'", ...(isDev ? ["'unsafe-eval'"] : [])];

  const directives: Record<string, string[]> = {
    "default-src": ["'self'"],
    "script-src": scripts,
    "style-src": ["'self'", "'unsafe-inline'"],
    "img-src": ["'self'", "data:", "https:"],
    "font-src": ["'self'", "data:"],
    "connect-src": connect,
    "object-src": ["'none'"],
    "base-uri": ["'self'"],
    "form-action": ["'self'"],
    "frame-ancestors": ["'none'"],
  };
  return Object.entries(directives)
    .map(([name, values]) => `${name} ${values.join(" ")}`)
    .join("; ");
}

/** 128 bits of randomness, base64 (CSP nonces must be unguessable and unique per response). */
export function generateNonce(): string {
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  let binary = "";
  bytes.forEach((b) => (binary += String.fromCharCode(b)));
  return btoa(binary);
}
