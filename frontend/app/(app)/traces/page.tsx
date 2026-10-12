"use client";

import React, { useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { ChevronDown, ChevronRight } from "lucide-react";
import { AgentOverview } from "@/components/agent/AgentOverview";
import { WorkflowDiagram } from "@/components/agent/WorkflowDiagram";
import { RunStatusBadge } from "@/components/ui/Badge";
import { Pagination } from "@/components/ui/Pagination";
import { EmptyState, ErrorState, PageHeader, Panel, PanelHeader, Skeleton } from "@/components/ui/Primitives";
import { api } from "@/lib/api-client";
import { formatDateTime, formatMs, timeAgo } from "@/lib/format";
import { keys, POLL_MS } from "@/lib/hooks";
import { agentName, classifierLabel, specialistOf } from "@/lib/workflow";
import type { AgentExecutionTrace } from "@/types";

const PAGE_SIZE = 15;

function Row({ run }: { run: AgentExecutionTrace }) {
  const [open, setOpen] = useState(false);
  const agent = specialistOf(run);
  return (
    <>
      <tr className="cursor-pointer transition-colors hover:bg-surface-2/60" onClick={() => setOpen((v) => !v)}>
        <td className="w-8 pl-3">
          <button type="button" aria-expanded={open} aria-label={open ? "Hide workflow" : "Show workflow"} className="text-fg-faint">
            {open ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
          </button>
        </td>
        <td className="whitespace-nowrap px-3 py-2.5 text-fg-muted">
          <time dateTime={run.started_at} title={formatDateTime(run.started_at)}>{timeAgo(run.started_at)}</time>
        </td>
        <td className="num px-3 py-2.5 text-fg">{run.intent ?? "UNKNOWN"}</td>
        <td className="px-3 py-2.5 text-fg-muted">{agent ? agentName(agent) : "Supervisor only"}</td>
        <td className="px-3 py-2.5 text-fg-muted">{classifierLabel(run.classifier)}</td>
        <td className="num px-3 py-2.5 text-right text-fg-muted">{run.tool_calls_made.length}</td>
        <td className="num px-3 py-2.5 text-right">{formatMs(run.total_duration_ms)}</td>
        <td className="px-3 py-2.5"><RunStatusBadge status={run.status} /></td>
      </tr>
      {open && (
        <tr className="bg-surface-2/40">
          <td />
          <td colSpan={7} className="px-3 pb-4 pt-2">
            <WorkflowDiagram run={run} orientation="horizontal" />
            <p className="num mt-2 text-[10px] text-fg-faint">Run {run.request_id}</p>
          </td>
        </tr>
      )}
    </>
  );
}

export default function TracesPage() {
  const [page, setPage] = useState(1);

  const overview = useQuery({
    queryKey: [...keys.traces, "overview"],
    queryFn: () => api.chat.traces({ limit: 100 }),
    refetchInterval: POLL_MS,
  });
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: [...keys.traces, "page", page],
    queryFn: () => api.chat.traces({ limit: PAGE_SIZE, offset: (page - 1) * PAGE_SIZE }),
    placeholderData: keepPreviousData,
    refetchInterval: POLL_MS,
  });

  const meta = data ? { page, page_size: PAGE_SIZE, total: data.total, total_pages: Math.ceil(data.total / PAGE_SIZE) } : null;

  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader
        title="Agent workflow"
        description="See what the agents did: who understood each request, which agent handled it, which tools ran, and how long every step took."
      />

      <AgentOverview runs={overview.data?.items} loading={overview.isLoading} />

      <Panel>
        <PanelHeader title="Run history" description="Open a run to see its workflow." />
        {error ? (
          <div className="p-4"><ErrorState title="Could not load agent runs" error={error} onRetry={() => void refetch()} /></div>
        ) : isLoading ? (
          <div className="p-4"><Skeleton className="h-40 w-full" /></div>
        ) : !data || data.items.length === 0 ? (
          <div className="p-4">
            <EmptyState title="No agent runs yet" description="Ask ORBIT something from the agent panel or Google Chat and its workflow appears here." />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] text-left text-[12.5px]">
              <thead className="border-b border-line text-[11px] font-semibold uppercase tracking-[0.05em] text-fg-faint">
                <tr>
                  <th className="w-8" />
                  <th scope="col" className="px-3 py-2">When</th>
                  <th scope="col" className="px-3 py-2">Intent</th>
                  <th scope="col" className="px-3 py-2">Handled by</th>
                  <th scope="col" className="px-3 py-2">Understood with</th>
                  <th scope="col" className="px-3 py-2 text-right">Tools</th>
                  <th scope="col" className="px-3 py-2 text-right">Duration</th>
                  <th scope="col" className="px-3 py-2">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line-subtle">{data.items.map((run) => <Row key={run.id} run={run} />)}</tbody>
            </table>
          </div>
        )}
      </Panel>
      {meta && meta.total_pages > 1 && <Pagination meta={meta} noun="runs" onPageChange={setPage} />}
    </div>
  );
}
