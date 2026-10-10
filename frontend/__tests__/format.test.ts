import { describe, expect, it } from "vitest";
import { daysUntil, describeAudit, formatDue, formatMs, humanize, initials, isOverdue, parseDateOnly, percent, timeAgo } from "@/lib/format";

const NOW = new Date(2026, 9, 10, 15, 30); // Oct 10 2026, mid-afternoon local time

describe("dates", () => {
  it("parses YYYY-MM-DD as a local calendar date, never shifted by timezone", () => {
    const d = parseDateOnly("2026-10-10");
    expect([d.getFullYear(), d.getMonth(), d.getDate()]).toEqual([2026, 9, 10]);
  });

  it("counts whole days from today regardless of the time of day", () => {
    expect(daysUntil("2026-10-10", NOW)).toBe(0);
    expect(daysUntil("2026-10-11", NOW)).toBe(1);
    expect(daysUntil("2026-10-07", NOW)).toBe(-3);
    expect(daysUntil("2026-10-10", new Date(2026, 9, 10, 0, 1))).toBe(0);
    expect(daysUntil("2026-10-10", new Date(2026, 9, 10, 23, 59))).toBe(0);
  });

  it("labels due dates in plain language", () => {
    expect(formatDue("2026-10-10", NOW)).toBe("Today");
    expect(formatDue("2026-10-11", NOW)).toBe("Tomorrow");
    expect(formatDue("2026-10-09", NOW)).toBe("1d overdue");
    expect(formatDue("2026-10-05", NOW)).toBe("5d overdue");
    expect(formatDue("2026-10-15", NOW)).toBe("in 5d");
    expect(formatDue("2026-12-25", NOW)).toMatch(/Dec/);
  });

  it("treats a task due today as not yet overdue", () => {
    expect(isOverdue({ due_date: "2026-10-10", status: "TODO" }, NOW)).toBe(false);
    expect(isOverdue({ due_date: "2026-10-09", status: "TODO" }, NOW)).toBe(true);
  });

  it("never marks finished or undated tasks overdue", () => {
    expect(isOverdue({ due_date: "2026-01-01", status: "DONE" }, NOW)).toBe(false);
    expect(isOverdue({ due_date: "2026-01-01", status: "CANCELLED" }, NOW)).toBe(false);
    expect(isOverdue({ due_date: null, status: "TODO" }, NOW)).toBe(false);
  });

  it("formats relative times", () => {
    const ago = (ms: number) => new Date(NOW.getTime() - ms).toISOString();
    expect(timeAgo(ago(10_000), NOW)).toBe("just now");
    expect(timeAgo(ago(5 * 60_000), NOW)).toBe("5m ago");
    expect(timeAgo(ago(3 * 3_600_000), NOW)).toBe("3h ago");
    expect(timeAgo(ago(2 * 86_400_000), NOW)).toBe("2d ago");
  });
});

describe("small formatters", () => {
  it("formats durations", () => {
    expect(formatMs(412)).toBe("412ms");
    expect(formatMs(1530)).toBe("1.5s");
    expect(formatMs(undefined)).toBe("");
  });
  it("formats fractions as whole percentages", () => {
    expect(percent(0.714)).toBe("71%");
    expect(percent(0)).toBe("0%");
    expect(percent(undefined)).toBe("0%");
  });
  it("derives initials", () => {
    expect(initials("John Doe")).toBe("JD");
    expect(initials("Sarah Jane Connor")).toBe("SC");
    expect(initials("admin")).toBe("AD");
    expect(initials("")).toBe("?");
    expect(initials(null)).toBe("?");
  });
  it("humanizes enum values", () => {
    expect(humanize("IN_PROGRESS")).toBe("In progress");
  });
});

describe("describeAudit", () => {
  const user = { display_name: "Sarah" } as never;

  it("describes lifecycle actions", () => {
    expect(describeAudit({ action: "CREATED", user, source: "api" })).toBe("Sarah created the task");
    expect(describeAudit({ action: "COMPLETED", user, source: "chat" })).toBe("Sarah marked the task done");
    expect(describeAudit({ action: "DELETED", user, source: "api" })).toBe("Sarah deleted the task");
  });

  it("describes field changes as sentences, not JSON", () => {
    const text = describeAudit({
      action: "UPDATED",
      user,
      source: "api",
      changes: { priority: { old: "MEDIUM", new: "HIGH" } },
    });
    expect(text).toBe("Sarah changed priority from Medium to High");
    expect(text).not.toContain("{");
  });

  it("does not leak raw ids when the assignee changes", () => {
    const text = describeAudit({
      action: "UPDATED",
      user,
      source: "api",
      changes: { assignee_id: { old: null, new: "3f2c9d1e-0000-0000-0000-000000000000" } },
    });
    expect(text).toBe("Sarah changed the assignee");
  });

  it("falls back gracefully without an actor or changes", () => {
    expect(describeAudit({ action: "UPDATED", source: "api" })).toBe("Someone updated the task");
    expect(describeAudit({ action: "UPDATED", source: "scheduler" })).toBe("ORBIT updated the task");
  });

  it("hides completed_at noise on status changes", () => {
    const text = describeAudit({
      action: "STATUS_CHANGED",
      user,
      source: "api",
      changes: { status: { old: "TODO", new: "IN_PROGRESS" }, completed_at: { old: "set", new: null } },
    });
    expect(text).toBe("Sarah changed status from To do to In progress");
  });
});
