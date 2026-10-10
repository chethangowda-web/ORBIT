import { describe, expect, it } from "vitest";
import { DEFAULT_VIEW, hasActiveFilters, nextSort, parseView, serializeView, toApiFilters } from "@/lib/task-query";

const parse = (qs: string) => parseView(new URLSearchParams(qs));

describe("parseView", () => {
  it("returns defaults for an empty query", () => {
    expect(parse("")).toEqual(DEFAULT_VIEW);
  });

  it("reads known filters", () => {
    expect(parse("q=deploy&status=TODO&priority=HIGH&assignee=me&overdue=1&sort=title&dir=desc&page=3")).toEqual({
      q: "deploy",
      status: "TODO",
      priority: "HIGH",
      assignee: "me",
      overdue: true,
      sortBy: "title",
      sortDir: "desc",
      page: 3,
    });
  });

  it("ignores unknown or tampered values instead of passing them to the API", () => {
    const view = parse("status=BOGUS&priority=URGENT&sort=password&dir=sideways&page=-4");
    expect(view.status).toBe("");
    expect(view.priority).toBe("");
    expect(view.sortBy).toBe("due_date");
    expect(view.sortDir).toBe("asc");
    expect(view.page).toBe(1);
  });

  it("rejects non-integer pages", () => {
    expect(parse("page=2.5").page).toBe(1);
    expect(parse("page=abc").page).toBe(1);
  });
});

describe("serializeView", () => {
  it("omits defaults so URLs stay clean", () => {
    expect(serializeView(DEFAULT_VIEW)).toBe("");
  });

  it("round-trips a full view", () => {
    const view = parse("q=api&status=REVIEW&assignee=abc&sort=priority&dir=desc&page=2");
    expect(parse(serializeView(view))).toEqual(view);
  });
});

describe("toApiFilters", () => {
  const now = new Date(2026, 9, 10, 12, 0);

  it("maps 'me' to the signed-in user", () => {
    expect(toApiFilters({ ...DEFAULT_VIEW, assignee: "me" }, "user-1", 15, now).assignee_id).toBe("user-1");
  });

  it("passes other assignee ids through", () => {
    expect(toApiFilters({ ...DEFAULT_VIEW, assignee: "user-9" }, "user-1", 15, now).assignee_id).toBe("user-9");
  });

  it("trims search text and omits empty fields", () => {
    const filters = toApiFilters({ ...DEFAULT_VIEW, q: "  deploy " }, undefined, 15, now);
    expect(filters.q).toBe("deploy");
    expect(filters.status).toBeUndefined();
    expect(filters.assignee_id).toBeUndefined();
  });

  it("overdue means due on or before yesterday and still open", () => {
    const filters = toApiFilters({ ...DEFAULT_VIEW, overdue: true }, undefined, 15, now);
    expect(filters.due_before).toBe("2026-10-09");
    expect(filters.include_completed).toBe(false);
  });

  it("overdue handles month boundaries", () => {
    const first = new Date(2026, 10, 1, 9, 0);
    expect(toApiFilters({ ...DEFAULT_VIEW, overdue: true }, undefined, 15, first).due_before).toBe("2026-10-31");
  });

  it("carries paging and sorting", () => {
    const filters = toApiFilters({ ...DEFAULT_VIEW, page: 4, sortBy: "title", sortDir: "desc" }, undefined, 15, now);
    expect(filters).toMatchObject({ page: 4, page_size: 15, sort_by: "title", sort_dir: "desc" });
  });
});

describe("helpers", () => {
  it("detects active filters", () => {
    expect(hasActiveFilters(DEFAULT_VIEW)).toBe(false);
    expect(hasActiveFilters({ ...DEFAULT_VIEW, overdue: true })).toBe(true);
    expect(hasActiveFilters({ ...DEFAULT_VIEW, q: "x" })).toBe(true);
  });

  it("toggles sort direction on the same column and resets on a new one", () => {
    expect(nextSort({ ...DEFAULT_VIEW, sortBy: "title", sortDir: "asc" }, "title")).toEqual({ sortBy: "title", sortDir: "desc" });
    expect(nextSort({ ...DEFAULT_VIEW, sortBy: "title", sortDir: "desc" }, "title")).toEqual({ sortBy: "title", sortDir: "asc" });
    expect(nextSort({ ...DEFAULT_VIEW, sortBy: "title", sortDir: "desc" }, "priority")).toEqual({ sortBy: "priority", sortDir: "asc" });
  });
});
