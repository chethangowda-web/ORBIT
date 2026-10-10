import type { BulkAction, BulkResult } from "@/types";

const PAST_TENSE: Record<BulkAction, string> = {
  complete: "Completed",
  set_status: "Updated status of",
  set_priority: "Updated priority of",
  assign: "Reassigned",
  delete: "Deleted",
};

/** One readable line for a bulk result, including why anything failed. */
export function summarizeBulk(action: BulkAction, result: BulkResult): string {
  const done = result.succeeded.length;
  const noun = (n: number) => `${n} task${n === 1 ? "" : "s"}`;
  if (result.failed.length === 0) return `${PAST_TENSE[action]} ${noun(done)}`;

  const reasons = Array.from(new Set(result.failed.map((f) => f.reason)));
  const shown = reasons.slice(0, 2).join("; ") + (reasons.length > 2 ? "; and more" : "");
  const head = done > 0 ? `${PAST_TENSE[action]} ${noun(done)}, ` : "";
  return `${head}${noun(result.failed.length)} failed: ${shown}`;
}

/** Selection helpers kept pure so the table logic is unit-testable. */
export function toggleId(selected: ReadonlySet<string>, id: string): Set<string> {
  const next = new Set(selected);
  if (next.has(id)) next.delete(id);
  else next.add(id);
  return next;
}

export function togglePage(selected: ReadonlySet<string>, pageIds: string[]): Set<string> {
  const allSelected = pageIds.length > 0 && pageIds.every((id) => selected.has(id));
  const next = new Set(selected);
  for (const id of pageIds) {
    if (allSelected) next.delete(id);
    else next.add(id);
  }
  return next;
}

export type PageSelection = "none" | "some" | "all";

export function pageSelectionState(selected: ReadonlySet<string>, pageIds: string[]): PageSelection {
  const count = pageIds.filter((id) => selected.has(id)).length;
  if (count === 0) return "none";
  return count === pageIds.length ? "all" : "some";
}
