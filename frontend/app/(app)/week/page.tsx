"use client";

import React from "react";
import Link from "next/link";
import { AlertTriangle, CalendarDays } from "lucide-react";
import { PriorityBadge } from "@/components/ui/Badge";
import { EmptyState, ErrorState, PageHeader, Panel, PanelHeader, Skeleton } from "@/components/ui/Primitives";
import { useWeekPlan } from "@/lib/hooks";
import type { PlannedTask, TaskPriority } from "@/types";

function TaskLine({ task, flagged }: { task: PlannedTask; flagged?: boolean }) {
  return (
    <li className="py-2">
      <div className="flex items-start justify-between gap-2">
        <Link href={`/tasks/${task.id}`} className="min-w-0 flex-1 text-[13px] font-medium text-fg hover:underline">
          {flagged && <AlertTriangle className="mr-1 inline h-3.5 w-3.5 text-warn" aria-label="Tight deadline" />}
          {task.title}
        </Link>
        <PriorityBadge priority={task.priority as TaskPriority} />
      </div>
      <p className="mt-0.5 text-[11px] text-fg-muted">
        {task.days_late > 0 ? <span className="text-danger">{task.days_late} day{task.days_late === 1 ? "" : "s"} late</span> : task.due_date ? `Due ${task.due_date}` : "No due date"}
        {task.note ? ` · ${task.note}` : ""}
      </p>
    </li>
  );
}

export default function WeekPage() {
  const { data, isLoading, error, refetch } = useWeekPlan();
  const planned = data ? data.days.reduce((n, d) => n + d.tasks.length, 0) : 0;

  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader
        title="My week"
        description="Your open tasks arranged over the next five working days. Late work comes first, then whatever is due soonest."
      />

      {error ? (
        <ErrorState title="Could not plan your week" error={error} onRetry={() => void refetch()} />
      ) : isLoading || !data ? (
        <Skeleton className="h-64 w-full" />
      ) : planned === 0 && data.later.length === 0 ? (
        <EmptyState title="Your week is clear" description="Nothing is assigned to you right now. New tasks will appear here." />
      ) : (
        <>
          {data.late_count > 0 && (
            <p role="status" className="mb-3 rounded-control border border-danger/30 bg-danger/5 px-3 py-2 text-xs text-fg">
              {data.late_count} task{data.late_count === 1 ? " is" : "s are"} already late, so {data.late_count === 1 ? "it comes" : "they come"} first.
            </p>
          )}
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
            {data.days.map((day) => (
              <Panel key={day.date}>
                <PanelHeader title={day.label} description={`${day.tasks.length} task${day.tasks.length === 1 ? "" : "s"}`} icon={<CalendarDays className="h-4 w-4" />} />
                <ul className="divide-y divide-line-subtle px-4">
                  {day.tasks.length === 0 ? (
                    <li className="py-3 text-xs text-fg-faint">Nothing planned</li>
                  ) : (
                    day.tasks.map((t) => <TaskLine key={t.id} task={t} flagged={data.at_risk.some((r) => r.id === t.id)} />)
                  )}
                </ul>
              </Panel>
            ))}
          </div>

          {data.at_risk.length > 0 && (
            <Panel className="mt-4 border-warn/40">
              <PanelHeader title="Tight spots" description="These are due this week, but the days before them are already full." icon={<AlertTriangle className="h-4 w-4 text-warn" />} />
              <ul className="divide-y divide-line-subtle px-4 text-[13px]">
                {data.at_risk.map((t) => (
                  <li key={t.id} className="py-2">
                    <span className="font-medium text-fg">{t.title}</span>
                    <span className="text-fg-muted">: {t.note}. Ask ORBIT to move the due date, or hand it to a teammate.</span>
                  </li>
                ))}
              </ul>
            </Panel>
          )}

          {data.later.length > 0 && (
            <Panel className="mt-4">
              <PanelHeader title="Later" description="These did not fit this week." />
              <ul className="divide-y divide-line-subtle px-4">
                {data.later.map((t) => <TaskLine key={t.id} task={t} />)}
              </ul>
            </Panel>
          )}
        </>
      )}
    </div>
  );
}
