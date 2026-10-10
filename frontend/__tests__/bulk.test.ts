import { describe, expect, it } from "vitest";
import { pageSelectionState, summarizeBulk, toggleId, togglePage } from "@/lib/bulk";
import { describeAudit } from "@/lib/format";

describe("summarizeBulk", () => {
  it("reports plain success", () => {
    expect(summarizeBulk("complete", { succeeded: ["a", "b", "c"], failed: [] })).toBe("Completed 3 tasks");
    expect(summarizeBulk("delete", { succeeded: ["a"], failed: [] })).toBe("Deleted 1 task");
  });

  it("explains partial failures, deduplicating identical reasons", () => {
    const text = summarizeBulk("complete", {
      succeeded: ["a"],
      failed: [
        { id: "b", reason: "You do not have permission to complete this task." },
        { id: "c", reason: "You do not have permission to complete this task." },
      ],
    });
    expect(text).toBe("Completed 1 task, 2 tasks failed: You do not have permission to complete this task.");
  });

  it("handles total failure and caps the reasons shown", () => {
    const text = summarizeBulk("set_status", {
      succeeded: [],
      failed: [
        { id: "a", reason: "r1" },
        { id: "b", reason: "r2" },
        { id: "c", reason: "r3" },
      ],
    });
    expect(text).toBe("3 tasks failed: r1; r2; and more");
  });
});

describe("selection helpers", () => {
  it("toggles one id without mutating the original set", () => {
    const original = new Set(["a"]);
    const added = toggleId(original, "b");
    expect([...added].sort()).toEqual(["a", "b"]);
    expect([...original]).toEqual(["a"]);
    expect([...toggleId(added, "a")]).toEqual(["b"]);
  });

  it("select-all selects every row on the page, a second press clears them", () => {
    const page = ["a", "b", "c"];
    const all = togglePage(new Set(), page);
    expect([...all].sort()).toEqual(page);
    expect(togglePage(all, page).size).toBe(0);
  });

  it("select-all completes a partial selection instead of clearing it", () => {
    const partial = new Set(["a"]);
    expect([...togglePage(partial, ["a", "b"])].sort()).toEqual(["a", "b"]);
  });

  it("clearing the page keeps selections made on other pages", () => {
    const next = togglePage(new Set(["a", "b", "z"]), ["a", "b"]);
    expect([...next]).toEqual(["z"]);
  });

  it("reports none, some and all", () => {
    expect(pageSelectionState(new Set(), ["a", "b"])).toBe("none");
    expect(pageSelectionState(new Set(["a"]), ["a", "b"])).toBe("some");
    expect(pageSelectionState(new Set(["a", "b"]), ["a", "b"])).toBe("all");
    expect(pageSelectionState(new Set(["a"]), [])).toBe("none");
  });
});

describe("comment audit entries", () => {
  it("read as a sentence", () => {
    const text = describeAudit({ action: "COMMENTED", user: { display_name: "Sarah" } as never, source: "api" });
    expect(text).toBe("Sarah commented");
  });
});
