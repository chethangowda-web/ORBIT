import { describe, expect, it } from "vitest";
import { buildCsp, generateNonce, originOf } from "@/lib/csp";

const directive = (csp: string, name: string) =>
  csp.split("; ").find((d) => d.startsWith(`${name} `))?.slice(name.length + 1).split(" ") ?? [];

describe("buildCsp", () => {
  const csp = buildCsp({ nonce: "abc123", apiUrl: "https://api.example.com/api" });

  it("only runs same-origin or nonced scripts, never inline or eval", () => {
    const scripts = directive(csp, "script-src");
    expect(scripts).toContain("'self'");
    expect(scripts).toContain("'nonce-abc123'");
    expect(scripts).toContain("'strict-dynamic'");
    expect(scripts).not.toContain("'unsafe-inline'");
    expect(scripts).not.toContain("'unsafe-eval'");
  });

  it("limits network calls to the app and its API origin (path stripped)", () => {
    expect(directive(csp, "connect-src")).toEqual(["'self'", "https://api.example.com"]);
  });

  it("blocks framing, plugins and foreign base or form targets", () => {
    expect(directive(csp, "frame-ancestors")).toEqual(["'none'"]);
    expect(directive(csp, "object-src")).toEqual(["'none'"]);
    expect(directive(csp, "base-uri")).toEqual(["'self'"]);
    expect(directive(csp, "form-action")).toEqual(["'self'"]);
    expect(directive(csp, "default-src")).toEqual(["'self'"]);
  });

  it("allows eval and websockets only in development", () => {
    const dev = buildCsp({ nonce: "n", apiUrl: "http://localhost:8001/api", isDev: true });
    expect(directive(dev, "script-src")).toContain("'unsafe-eval'");
    expect(directive(dev, "connect-src")).toContain("ws:");
    expect(directive(csp, "connect-src")).not.toContain("ws:");
  });

  it("copes with an unparseable API url", () => {
    expect(directive(buildCsp({ nonce: "n", apiUrl: "not a url" }), "connect-src")).toEqual(["'self'"]);
  });
});

describe("nonce and origin helpers", () => {
  it("generates unique, sufficiently long nonces", () => {
    const nonces = new Set(Array.from({ length: 50 }, generateNonce));
    expect(nonces.size).toBe(50);
    expect([...nonces][0].length).toBeGreaterThanOrEqual(22);
  });

  it("extracts origins", () => {
    expect(originOf("http://localhost:8001/api")).toBe("http://localhost:8001");
    expect(originOf("garbage")).toBeNull();
  });
});
