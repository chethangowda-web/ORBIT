import { describe, expect, it } from "vitest";
import { filterCommands, moveIndex, scoreCommand } from "@/lib/commands";

const cmd = (label: string, keywords: string[] = []) => ({ label, keywords, group: "Navigate" as const });

describe("scoreCommand", () => {
  it("ranks exact over prefix over word-start over substring over keyword", () => {
    const exact = scoreCommand(cmd("Board"), "board");
    const prefix = scoreCommand(cmd("Board view"), "boa");
    const wordStart = scoreCommand(cmd("Go to Board"), "boa");
    const substring = scoreCommand(cmd("Dashboard"), "board");
    const keyword = scoreCommand(cmd("Go to Tasks", ["table"]), "tab");
    expect([exact, prefix, wordStart, substring, keyword].every((n, i, a) => i === 0 || a[i - 1] > n)).toBe(true);
    expect(keyword).toBeGreaterThan(0);
  });

  it("is case and whitespace insensitive", () => {
    expect(scoreCommand(cmd("New task"), "  NEW ")).toBeGreaterThan(0);
  });

  it("returns 0 for no match and matches everything on an empty query", () => {
    expect(scoreCommand(cmd("New task"), "zzz")).toBe(0);
    expect(scoreCommand(cmd("New task"), "")).toBeGreaterThan(0);
  });
});

describe("filterCommands", () => {
  const commands = [cmd("Go to Insights", ["analytics"]), cmd("Go to Tasks"), cmd("New task", ["create", "add"])];

  it("keeps original order for an empty query", () => {
    expect(filterCommands(commands, "").map((c) => c.label)).toEqual(["Go to Insights", "Go to Tasks", "New task"]);
  });

  it("filters and orders by relevance", () => {
    expect(filterCommands(commands, "task").map((c) => c.label)).toEqual(["New task", "Go to Tasks"]);
  });

  it("finds commands by keyword", () => {
    expect(filterCommands(commands, "analytics").map((c) => c.label)).toEqual(["Go to Insights"]);
    expect(filterCommands(commands, "create").map((c) => c.label)).toEqual(["New task"]);
  });

  it("returns nothing when nothing matches", () => {
    expect(filterCommands(commands, "xyz")).toEqual([]);
  });
});

describe("moveIndex", () => {
  it("wraps around in both directions", () => {
    expect(moveIndex(0, -1, 3)).toBe(2);
    expect(moveIndex(2, 1, 3)).toBe(0);
    expect(moveIndex(1, 1, 3)).toBe(2);
  });
  it("is safe with an empty list", () => {
    expect(moveIndex(0, 1, 0)).toBe(0);
  });
});
