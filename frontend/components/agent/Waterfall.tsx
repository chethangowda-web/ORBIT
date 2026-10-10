import React from "react";
import { AGENT_LABEL } from "@/lib/constants";
import { formatMs } from "@/lib/format";

export function Waterfall({ durations, total }: { durations: Record<string, number>; total?: number }) {
  const entries = Object.entries(durations);
  if (entries.length === 0) return null;
  const max = Math.max(total ?? 0, ...entries.map(([, ms]) => ms), 1);
  return (
    <ul className="mt-1.5 space-y-1">
      {entries.map(([node, ms]) => (
        <li key={node} className="flex items-center gap-2">
          <span className="w-20 shrink-0 truncate text-[10px] text-fg-muted">{AGENT_LABEL[node] ?? node}</span>
          <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-surface-3">
            <span className="block h-full rounded-full bg-accent" style={{ width: `${Math.max(4, (ms / max) * 100)}%` }} />
          </span>
          <span className="num w-12 shrink-0 text-right text-[10px] text-fg-faint">{formatMs(ms)}</span>
        </li>
      ))}
    </ul>
  );
}
