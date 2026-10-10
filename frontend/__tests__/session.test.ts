import { describe, expect, it } from "vitest";
import { decodeTokenClaims, isAdminRole, isManagerRole, isTokenExpired, routeRequiresManager } from "@/lib/session";

function makeToken(claims: object): string {
  const encode = (value: object) => Buffer.from(JSON.stringify(value)).toString("base64url");
  return `${encode({ alg: "HS256", typ: "JWT" })}.${encode(claims)}.signature`;
}

describe("token claims", () => {
  it("decodes the payload", () => {
    const token = makeToken({ sub: "u1", role: "manager", exp: 2_000_000_000 });
    expect(decodeTokenClaims(token)).toMatchObject({ sub: "u1", role: "manager" });
  });

  it("returns null for anything that is not a JWT", () => {
    expect(decodeTokenClaims(undefined)).toBeNull();
    expect(decodeTokenClaims("")).toBeNull();
    expect(decodeTokenClaims("not-a-token")).toBeNull();
    expect(decodeTokenClaims("a.b.c")).toBeNull();
  });

  it("handles unicode in claims", () => {
    expect(decodeTokenClaims(makeToken({ email: "zoë@orbit.dev" }))?.email).toBe("zoë@orbit.dev");
  });
});

describe("expiry", () => {
  const now = 1_800_000_000;
  it("is expired when exp is in the past", () => {
    expect(isTokenExpired(makeToken({ exp: now - 10 }), now)).toBe(true);
  });
  it("is valid before exp", () => {
    expect(isTokenExpired(makeToken({ exp: now + 3600 }), now)).toBe(false);
  });
  it("treats tokens within a few seconds of expiry as expired to avoid mid-request 401s", () => {
    expect(isTokenExpired(makeToken({ exp: now + 2 }), now)).toBe(true);
  });
  it("treats missing or malformed tokens as expired", () => {
    expect(isTokenExpired(null, now)).toBe(true);
    expect(isTokenExpired("garbage", now)).toBe(true);
    expect(isTokenExpired(makeToken({ sub: "no-exp" }), now)).toBe(true);
  });
});

describe("roles and routes", () => {
  it("recognises manager and admin roles", () => {
    expect(isManagerRole("manager")).toBe(true);
    expect(isManagerRole("admin")).toBe(true);
    expect(isManagerRole("employee")).toBe(false);
    expect(isManagerRole(undefined)).toBe(false);
    expect(isAdminRole("admin")).toBe(true);
    expect(isAdminRole("manager")).toBe(false);
  });

  it("flags manager-only routes and their children", () => {
    expect(routeRequiresManager("/insights")).toBe(true);
    expect(routeRequiresManager("/admin")).toBe(true);
    expect(routeRequiresManager("/admin/users")).toBe(true);
    expect(routeRequiresManager("/tasks")).toBe(false);
    expect(routeRequiresManager("/")).toBe(false);
  });

  it("does not match look-alike prefixes", () => {
    expect(routeRequiresManager("/administrators")).toBe(false);
    expect(routeRequiresManager("/insightful")).toBe(false);
  });
});
