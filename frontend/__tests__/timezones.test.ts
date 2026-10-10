import { describe, expect, it } from "vitest";
import { timezoneOptions } from "@/lib/timezones";

describe("timezoneOptions", () => {
  it("always includes the stored zone even when the browser lists a different alias", () => {
    expect(timezoneOptions("Asia/Kolkata")).toContain("Asia/Kolkata");
    expect(timezoneOptions("Not/AZone")).toContain("Not/AZone");
  });

  it("includes UTC and has no duplicates", () => {
    const zones = timezoneOptions("UTC");
    expect(zones).toContain("UTC");
    expect(new Set(zones).size).toBe(zones.length);
  });

  it("is sorted for scanning", () => {
    const zones = timezoneOptions();
    expect(zones).toEqual([...zones].sort());
  });

  it("works without a current value", () => {
    expect(timezoneOptions().length).toBeGreaterThan(3);
  });
});
