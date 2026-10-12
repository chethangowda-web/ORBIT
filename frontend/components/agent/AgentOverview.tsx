"use client";

import React from "react";
import { ArrowDown, ArrowRight, Database, MessageSquare, Network, Wrench } from "lucide-react";
import { Panel, PanelHeader, Skeleton } from "@/components/ui/Primitives";
import { cn } from "@/lib/cn";
import { formatMs } from "@/lib/format";
import { AGENT_ROLE, SPECIALISTS, agentName, classifierLabel, summarizeRuns } from "@/lib/workflow";
import type { AgentExecutionTrace } from "@/types";
import { AGENT_ICON } from "./WorkflowDiagram";

/** The agent architecture with live numbers: what each agent does and how much it has been used. */
export function AgentOverview({ runs, loading }: { runs: AgentExecutionTrace[] | undefined; loading: boolean }) {
  const summary = summarizeRuns(runs ?? []);
  const SupervisorIcon = AGENT_ICON.supervisor;
  const mix = Object.entries(summary.classifier)
    .filter(([key]) => key !== "unknown")
    .map(([key, count]) => `${classifierLabel(key)} ${count}`)
    .join(" · ");

  return (
    <Panel className="mb-4">
      <PanelHeader
        title="How ORBIT works"
        description="Every request goes through the Supervisor to one specialist agent, which works with real tools and your permissions."
        icon={<Network className="h-4 w-4" />}
      />
      <div className="space-y-2 p-4">
        <div className="flex flex-col items-stretch gap-2 md:flex-row md:items-center">
          <div className="flex items-center gap-2 rounded-control border border-line bg-surface-2 px-3 py-2.5 md:w-56">
            <MessageSquare className="h-4 w-4 shrink-0 text-fg-muted" aria-hidden />
            <div>
              <p className="text-xs font-semibold text-fg">Your request</p>
              <p className="text-[11px] text-fg-muted">Google Chat or the dashboard</p>
            </div>
          </div>
          <ArrowRight className="hidden h-4 w-4 shrink-0 text-fg-faint md:block" aria-hidden />
          <ArrowDown className="mx-auto h-4 w-4 text-fg-faint md:hidden" aria-hidden />
          <div className="flex-1 rounded-control border border-accent/40 bg-accent/5 px-3 py-2.5">
            <div className="flex items-center gap-2">
              <SupervisorIcon className="h-4 w-4 shrink-0 text-accent" aria-hidden />
              <p className="text-xs font-semibold text-fg">Supervisor</p>
              <span className="num ml-auto text-[11px] text-fg-muted">
                {loading ? "" : summary.total === 0 ? "No requests yet" : `${summary.total} recent request${summary.total === 1 ? "" : "s"}`}
              </span>
            </div>
            <p className="mt-1 text-[11px] text-fg-muted">
              {AGENT_ROLE.supervisor}. Uses Gemini AI, with built-in rules as a fallback.
              {mix && <span className="num text-fg"> {mix}</span>}
            </p>
          </div>
        </div>

        <p className="flex items-center justify-center gap-1.5 py-1 text-[11px] text-fg-faint">
          <ArrowDown className="h-3.5 w-3.5" aria-hidden /> routes each request to one of
        </p>

        {loading ? (
          <Skeleton className="h-28 w-full" />
        ) : (
          <ul className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
            {SPECIALISTS.map((node) => {
              const Icon = AGENT_ICON[node];
              const stat = summary.byAgent[node];
              const latest = summary.lastAgent === node;
              return (
                <li key={node} className={cn("rounded-control border p-3", latest ? "border-accent bg-accent/5" : "border-line bg-surface-2")}>
                  <div className="flex items-center gap-2">
                    <Icon className={cn("h-4 w-4 shrink-0", latest ? "text-accent" : "text-fg-muted")} aria-hidden />
                    <p className="text-xs font-semibold text-fg">{agentName(node)}</p>
                    {latest && <span className="ml-auto rounded-full bg-accent/15 px-1.5 py-0.5 text-[9px] font-medium uppercase tracking-wide text-accent">Latest</span>}
                  </div>
                  <p className="mt-1.5 text-[11px] leading-snug text-fg-muted">{AGENT_ROLE[node]}</p>
                  <p className="num mt-2 text-[11px] text-fg-faint">
                    {stat ? `${stat.runs} run${stat.runs === 1 ? "" : "s"} · avg ${formatMs(stat.avgMs)}` : "No runs yet"}
                  </p>
                </li>
              );
            })}
          </ul>
        )}

        <p className="flex items-center justify-center gap-1.5 py-1 text-[11px] text-fg-faint">
          <ArrowDown className="h-3.5 w-3.5" aria-hidden /> use tools with your permissions
        </p>
        <div className="flex flex-col items-start gap-2 rounded-control border border-line bg-surface-2 px-3 py-2.5 text-[11px] text-fg-muted sm:flex-row sm:items-center">
          <span className="flex items-center gap-1.5 text-xs font-semibold text-fg">
            <Wrench className="h-3.5 w-3.5 text-fg-muted" aria-hidden /> Tools
          </span>
          <span>create, update, complete and search tasks, plan the day, read team workload</span>
          <span className="flex items-center gap-1.5 sm:ml-auto">
            <Database className="h-3.5 w-3.5" aria-hidden /> PostgreSQL for data, Redis for conversation memory
          </span>
        </div>
      </div>
    </Panel>
  );
}
