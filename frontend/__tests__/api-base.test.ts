import { describe, expect, it } from "vitest";
import { PROXY_PREFIX, resolveApiBase } from "@/lib/api-base";

describe("resolveApiBase", () => {
  const backend = "https://orbit-backend.onrender.com/api";

  it("goes straight to the backend on a normal address", () => {
    expect(resolveApiBase(backend, "localhost")).toBe(backend);
    expect(resolveApiBase(backend, "orbit.mycompany.com")).toBe(backend);
  });

  it("goes through the dashboard's own address on any vercel.app deployment", () => {
    expect(resolveApiBase(backend, "orbit-lyart-tau-78.vercel.app")).toBe(PROXY_PREFIX);
    expect(resolveApiBase(backend, "orbit-jm5hp13n7-chethann1328-7757s-projects.vercel.app")).toBe(PROXY_PREFIX);
  });

  it("does not look like vercel.app when it only contains the text", () => {
    expect(resolveApiBase(backend, "vercel.app.evil.com")).toBe(backend);
  });

  it("keeps a relative or default address as it is, and defaults to the local backend", () => {
    expect(resolveApiBase("/api", "x.vercel.app")).toBe("/api");
    expect(resolveApiBase(undefined, "localhost")).toBe("http://localhost:8001/api");
  });
});
