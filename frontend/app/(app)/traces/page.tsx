"use client";

import React, { useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { ChevronDown, ChevronRight } from "lucide-react";
import { Waterfall } from "@/components/agent/Waterfall";
import { RunStatusBadge } from "@/components/ui/Badge";
import { Pagination } from "@/components/ui/Pagination";
import { EmptyState, ErrorState, PageHeader, Panel, Skeleton } from "@/components/ui/Primitives";
import { api } from "@/lib/api-client";
import { AGENT_LABEL } from "@/lib/constants";
import { formatDateTime, formatMs, timeAgo } from "@/lib/format";
import { keys, POLL_MS } from "@/lib/hooks";
import type { AgentExecutionTrace } from "@/types";

const PAGE_SIZE = 20;

function Row({ run }: { run: AgentExecutionTrace }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <tr className="cursor-pointer transition-colors hover:bg-surface-2/60" onClick={() => setOpen((v) => !v)}>
        <td className="w-8 pl-3">
          <button type="button" aria-expanded={open} aria-label={open ? "Collapse run" : "Expand run"} className="text-fg-faint">
            {open ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
          </button>
        </td>
        <td className="whitespace-nowrap px-3 py-2.5 text-fg-muted">
          <time dateTime={run.started_at} title={formatDateTime(run.started_at)}>{timeAgo(run.started_at)}</time>
        </td>
        <td className="num px-3 py-2.5 text-fg">{run.intent ?? "UNKNOWN"}</td>
        <td className="px-3 py-2.5 text-fg-muted">{run.agents_invoked.map((a) => AGENT_LABEL[a] ?? a).join(" > ") || "Supervisor"}</td>
        <td className="num px-3 py-2.5 text-right text-fg-muted">{run.tool_calls_made.length}</td>
        <td className="num px-3 py-2.5 text-right">{formatMs(run.total_duration_ms)}</td>
        <td className="px-3 py-2.5"><RunStatusBadge status={run.status} /></td>
      </tr>
      {open && (
        <tr className="bg-surface-2/40">
          <td />
          <td colSpan={6} className="px-3 pb-4 pt-1 text-xs text-fg-muted">
            <div className="grid gap-4 md:grid-cols-2">
              <dl className="space-y-1.5">
                <div><dt className="inline text-fg-faint">Request </dt><dd className="num inline text-fg">{run.request_id}</dd></div>
                <div><dt className="inline text-fg-faint">Confidence </dt><dd className="num inline text-fg">{run.confidence != null ? `${Math.round(run.confidence * 100)}%` : "n/a"}</dd></div>
                <div><dt className="inline text-fg-faint">Tools </dt><dd className="num inline text-fg">{run.tool_calls_made.join(", ") || "none"}</dd></div>
                {run.error_message && <div className="text-danger">{run.error_code}: {run.error_message}</div>}
              </dl>
              <div>
                <p className="section-label mb-1">Time per agent</p>
                <Waterfall durations={run.node_durations_ms} total={run.total_duration_ms} />
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

export default function TracesPage() {
  const [page, setPage] = useState(1);
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: [...keys.traces, "page", page],
    queryFn: () => api.chat.traces({ limit: PAGE_SIZE, offset: (page - 1) * PAGE_SIZE }),
    placeholderData: keepPreviousData,
    refetchInterval: POLL_MS,
  });

  const meta = data ? { page, page_size: PAGE_SIZE, total: data.total, total_pages: Math.ceil(data.total / PAGE_SIZE) } : null;

  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader title="Agent runs" description="How ORBIT routed each of your requests: which agents ran, which tools they used, and how long each step took." />

      {error ? (
        <ErrorState title="Could not load agent runs" error={error} onRetry={() => void refetch()} />
      ) : isLoading ? (
        <Skeleton className="h-64 w-full" />
      ) : !data || data.items.length === 0 ? (
        <EmptyState title="No agent runs yet" description="Ask ORBIT something from the agent panel or Google Chat and the run appears here." />
      ) : (
        <>
          <Panel className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-left text-[12.5px]">
              <thead className="border-b border-line text-[11px] font-semibold uppercase tracking-[0.05em] text-fg-faint">
                <tr>
                  <th className="w-8" />
                  <th scope="col" className="px-3 py-2">When</th>
                  <th scope="col" className="px-3 py-2">Intent</th>
                  <th scope="col" className="px-3 py-2">Route</th>
                  <th scope="col" className="px-3 py-2 text-right">Tools</th>
                  <th scope="col" className="px-3 py-2 text-right">Duration</th>
                  <th scope="col" className="px-3 py-2">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line-subtle">{data.items.map((run) => <Row key={run.id} run={run} />)}</tbody>
            </table>
          </Panel>
          {meta && <Pagination meta={meta} noun="runs" onPageChange={setPage} />}
        </>
      )}
    </div>
  );
}
