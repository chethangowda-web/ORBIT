"use client";

import React from "react";
import { Lock, Orbit } from "lucide-react";
import { Panel, PanelHeader, Skeleton } from "@/components/ui/Primitives";
import { cn } from "@/lib/cn";
import { formatMs } from "@/lib/format";
import { AGENT_ROLE, SPECIALISTS, agentName, summarizeRuns } from "@/lib/workflow";
import type { AgentExecutionTrace } from "@/types";
import { AGENT_ICON } from "./WorkflowDiagram";

const MIX_LABEL: Record<string, string> = { llm: "by AI", quick: "by quick check", rules: "by quick check", flow: "from your answers" };

const SIZE = 400;
const CENTER = SIZE / 2;
const RING = 150;

/** Position of helper `index` on the ring, starting at the top and going clockwise. */
function place(index: number, count: number) {
  const angle = -Math.PI / 2 + (index * 2 * Math.PI) / count;
  return { x: CENTER + RING * Math.cos(angle), y: CENTER + RING * Math.sin(angle) };
}

/** ORBIT's team as a small solar system: the Coordinator in the middle, each helper on the ring around it. */
export function AgentOverview({ runs, loading }: { runs: AgentExecutionTrace[] | undefined; loading: boolean }) {
  const summary = summarizeRuns(runs ?? []);
  const CoordinatorIcon = AGENT_ICON.supervisor;
  const mix = Object.entries(summary.classifier)
    .filter(([key]) => key !== "unknown")
    .map(([key, count]) => `${count} ${MIX_LABEL[key] ?? key}`)
    .join(" · ");
  const pct = (n: number) => `${(n / SIZE) * 100}%`;

  return (
    <Panel className="mb-4">
      <PanelHeader
        title="Your ORBIT team"
        description="Every request reaches the Coordinator at the centre, who sends it to the right helper. Helpers only see what you are allowed to see."
        icon={<Orbit className="h-4 w-4" />}
      />
      {loading ? (
        <div className="p-4">
          <Skeleton className="h-72 w-full" />
        </div>
      ) : (
        <div className="grid items-center gap-6 p-4 lg:grid-cols-[minmax(0,420px)_1fr]">
          <div role="img" aria-label="Map of ORBIT's team: the Coordinator in the middle with five helpers around it" className="relative mx-auto aspect-square w-full max-w-[420px]">
            <svg viewBox={`0 0 ${SIZE} ${SIZE}`} className="absolute inset-0 h-full w-full" aria-hidden>
              <defs>
                <radialGradient id="orbit-core" cx="50%" cy="50%" r="50%">
                  <stop offset="0%" stopColor="rgb(var(--accent))" stopOpacity="0.35" />
                  <stop offset="100%" stopColor="rgb(var(--accent))" stopOpacity="0" />
                </radialGradient>
              </defs>
              <circle cx={CENTER} cy={CENTER} r={RING + 40} fill="url(#orbit-core)" opacity="0.5" />
              <circle cx={CENTER} cy={CENTER} r={RING} fill="none" className="stroke-line" strokeWidth="1.5" strokeDasharray="3 7" />
              <circle cx={CENTER} cy={CENTER} r={RING - 70} fill="none" className="stroke-line-subtle" strokeWidth="1" />
              {SPECIALISTS.map((node, i) => {
                const { x, y } = place(i, SPECIALISTS.length);
                const latest = summary.lastAgent === node;
                return (
                  <line
                    key={node}
                    x1={CENTER}
                    y1={CENTER}
                    x2={x}
                    y2={y}
                    className={latest ? "stroke-accent" : "stroke-line"}
                    strokeWidth={latest ? 2 : 1}
                    strokeDasharray={latest ? "6 6" : undefined}
                  >
                    {latest && <animate attributeName="stroke-dashoffset" from="24" to="0" dur="1.2s" repeatCount="indefinite" />}
                  </line>
                );
              })}
            </svg>

            <div
              className="absolute flex h-24 w-24 -translate-x-1/2 -translate-y-1/2 flex-col items-center justify-center rounded-full border-2 border-accent/60 bg-surface-1 text-center shadow-lg"
              style={{ left: pct(CENTER), top: pct(CENTER) }}
            >
              <CoordinatorIcon className="h-5 w-5 text-accent" aria-hidden />
              <span className="mt-0.5 text-[11px] font-semibold text-fg">Coordinator</span>
              <span className="num text-[10px] text-fg-muted">{summary.total === 0 ? "no requests yet" : `${summary.total} request${summary.total === 1 ? "" : "s"}`}</span>
            </div>

            {SPECIALISTS.map((node, i) => {
              const { x, y } = place(i, SPECIALISTS.length);
              const Icon = AGENT_ICON[node];
              const stat = summary.byAgent[node];
              const latest = summary.lastAgent === node;
              return (
                <div key={node} className="absolute flex w-24 -translate-x-1/2 -translate-y-1/2 flex-col items-center text-center" style={{ left: pct(x), top: pct(y) }}>
                  <span className="relative flex h-12 w-12 items-center justify-center">
                    {latest && <span className="absolute inset-0 animate-ping rounded-full bg-accent/30 motion-reduce:animate-none" aria-hidden />}
                    <span
                      className={cn(
                        "relative flex h-12 w-12 items-center justify-center rounded-full border-2 bg-surface-1",
                        latest ? "border-accent text-accent" : stat ? "border-fg-faint text-fg" : "border-line text-fg-faint"
                      )}
                    >
                      <Icon className="h-5 w-5" aria-hidden />
                    </span>
                    {stat && (
                      <span className="num absolute -right-1 -top-1 flex h-5 min-w-5 items-center justify-center rounded-full bg-accent px-1 text-[10px] font-semibold text-white">
                        {stat.runs}
                      </span>
                    )}
                  </span>
                  <span className="relative mt-1 rounded bg-surface-1/80 px-1 text-[11px] font-medium leading-tight text-fg">{agentName(node)}</span>
                </div>
              );
            })}
          </div>

          <div className="space-y-3">
            <p className="text-[12px] leading-relaxed text-fg-muted">
              {AGENT_ROLE.supervisor}. It uses AI, with a quick backup when the AI is busy.
              {mix && <span className="num text-fg"> Understood {mix}.</span>}
            </p>
            <ul className="divide-y divide-line-subtle rounded-control border border-line bg-surface-2">
              {SPECIALISTS.map((node) => {
                const Icon = AGENT_ICON[node];
                const stat = summary.byAgent[node];
                const latest = summary.lastAgent === node;
                return (
                  <li key={node} className="flex items-start gap-3 px-3 py-2.5">
                    <Icon className={cn("mt-0.5 h-4 w-4 shrink-0", latest ? "text-accent" : "text-fg-muted")} aria-hidden />
                    <div className="min-w-0 flex-1">
                      <p className="flex items-center gap-2 text-xs font-semibold text-fg">
                        {agentName(node)}
                        {latest && <span className="rounded-full bg-accent/15 px-1.5 py-0.5 text-[9px] font-medium uppercase tracking-wide text-accent">Latest</span>}
                      </p>
                      <p className="text-[11px] leading-snug text-fg-muted">{AGENT_ROLE[node]}</p>
                    </div>
                    <p className="num shrink-0 text-right text-[11px] text-fg-faint">
                      {stat ? `Helped ${stat.runs} time${stat.runs === 1 ? "" : "s"}` : "Hasn't helped yet"}
                      {stat && <span className="block">usually {formatMs(stat.avgMs)}</span>}
                    </p>
                  </li>
                );
              })}
            </ul>
            <p className="flex items-center gap-1.5 text-[11px] text-fg-faint">
              <Lock className="h-3.5 w-3.5 shrink-0" aria-hidden /> Helpers only act on what you are allowed to see. Everything is saved safely, and ORBIT remembers the conversation.
            </p>
          </div>
        </div>
      )}
    </Panel>
  );
}
