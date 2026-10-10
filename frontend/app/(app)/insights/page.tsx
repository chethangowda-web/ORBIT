"use client";

import React from "react";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { EmptyState, ErrorState, MetricTile, PageHeader, Panel, PanelHeader, Skeleton } from "@/components/ui/Primitives";
import { ALL_STATUSES, CHART_COLORS, PRIORITIES, PRIORITY_CHART_COLOR, PRIORITY_LABEL, STATUS_CHART_COLOR, STATUS_LABEL } from "@/lib/constants";
import { percent } from "@/lib/format";
import { useStats, useWorkload } from "@/lib/hooks";
import type { TaskPriority, TaskStatus } from "@/types";

const tooltipStyle = {
  contentStyle: { background: CHART_COLORS.surface, border: `1px solid ${CHART_COLORS.line}`, borderRadius: 6, fontSize: 12, color: CHART_COLORS.text },
  itemStyle: { color: CHART_COLORS.text },
  labelStyle: { color: CHART_COLORS.muted },
  cursor: { fill: "rgb(var(--fg) / 0.06)" },
};

const axisProps = { stroke: CHART_COLORS.faint, fontSize: 11, tickLine: false, axisLine: { stroke: CHART_COLORS.line } } as const;

function ChartPanel({ title, description, empty, children }: { title: string; description?: string; empty?: boolean; children: React.ReactNode }) {
  return (
    <Panel>
      <PanelHeader title={title} description={description} />
      <div className="h-64 p-4">
        {empty ? <EmptyState title="No data yet" description="Charts fill in as tasks are created." className="h-full" /> : children}
      </div>
    </Panel>
  );
}

export default function InsightsPage() {
  const stats = useStats();
  const workload = useWorkload(true);

  if (stats.error) return <ErrorState title="Could not load insights" error={stats.error} onRetry={() => void stats.refetch()} />;

  const data = stats.data;
  const statusData = ALL_STATUSES.map((s: TaskStatus) => ({ key: s, name: STATUS_LABEL[s], value: data?.by_status?.[s] ?? 0 })).filter((d) => d.value > 0);
  const priorityData = PRIORITIES.map((p: TaskPriority) => ({ key: p, name: PRIORITY_LABEL[p], tasks: data?.by_priority?.[p] ?? 0 }));
  const trend = (data?.tasks_created_per_day ?? []).map((d) => ({ ...d, label: d.date.slice(5) }));
  const people = (workload.data ?? []).filter((w) => w.assigned_tasks > 0);

  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader title="Insights" description="Live aggregates from the task database." />

      <div className="mb-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <MetricTile label="Completion rate" value={percent(data?.completion_rate)} tone="ok" loading={stats.isLoading} hint={data ? `${data.completed_tasks} of ${data.total_tasks} tasks done` : undefined} />
        <MetricTile label="Avg time to done" value={data && data.avg_completion_days > 0 ? `${data.avg_completion_days}d` : "n/a"} loading={stats.isLoading} hint="Created to completed" />
        <MetricTile label="Overdue" value={data?.overdue_tasks ?? 0} tone={data?.overdue_tasks ? "danger" : "default"} loading={stats.isLoading} href="/tasks?overdue=1" hint="Open tasks past due" />
        <MetricTile label="People with work" value={people.length} tone="info" loading={workload.isLoading} hint="Active assignees" />
      </div>

      {stats.isLoading ? (
        <div className="grid gap-4 lg:grid-cols-2">
          {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-72" />)}
        </div>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          <ChartPanel title="Status mix" empty={statusData.length === 0}>
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={statusData} dataKey="value" nameKey="name" innerRadius={55} outerRadius={80} paddingAngle={3} stroke="none" isAnimationActive={false}>
                  {statusData.map((d) => <Cell key={d.key} fill={STATUS_CHART_COLOR[d.key]} />)}
                </Pie>
                <Tooltip {...tooltipStyle} />
                <Legend iconType="circle" wrapperStyle={{ fontSize: 11, color: CHART_COLORS.muted }} />
              </PieChart>
            </ResponsiveContainer>
          </ChartPanel>

          <ChartPanel title="Priority mix" empty={priorityData.every((d) => d.tasks === 0)}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={priorityData} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
                <CartesianGrid vertical={false} stroke={CHART_COLORS.grid} />
                <XAxis dataKey="name" {...axisProps} />
                <YAxis allowDecimals={false} {...axisProps} />
                <Tooltip {...tooltipStyle} />
                <Bar dataKey="tasks" name="Tasks" radius={[4, 4, 0, 0]} isAnimationActive={false}>
                  {priorityData.map((d) => <Cell key={d.key} fill={PRIORITY_CHART_COLOR[d.key]} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </ChartPanel>

          <ChartPanel title="Created per day" description="Last 14 days" empty={trend.every((d) => d.count === 0)}>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={trend} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
                <CartesianGrid vertical={false} stroke={CHART_COLORS.grid} />
                <XAxis dataKey="label" {...axisProps} interval="preserveStartEnd" />
                <YAxis allowDecimals={false} {...axisProps} />
                <Tooltip {...tooltipStyle} />
                <Area type="monotone" dataKey="count" name="Created" stroke={CHART_COLORS.accent} fill={CHART_COLORS.accent} fillOpacity={0.15} strokeWidth={2} isAnimationActive={false} />
              </AreaChart>
            </ResponsiveContainer>
          </ChartPanel>

          <ChartPanel title="Workload by person" empty={people.length === 0}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={people} layout="vertical" margin={{ top: 4, right: 12, left: 8, bottom: 0 }}>
                <CartesianGrid horizontal={false} stroke={CHART_COLORS.grid} />
                <XAxis type="number" allowDecimals={false} {...axisProps} />
                <YAxis type="category" dataKey="display_name" width={96} {...axisProps} />
                <Tooltip {...tooltipStyle} />
                <Legend iconType="circle" wrapperStyle={{ fontSize: 11, color: CHART_COLORS.muted }} />
                <Bar dataKey="assigned_tasks" name="Assigned" fill={CHART_COLORS.info} radius={[0, 3, 3, 0]} isAnimationActive={false} />
                <Bar dataKey="completed_tasks" name="Done" fill={CHART_COLORS.ok} radius={[0, 3, 3, 0]} isAnimationActive={false} />
                <Bar dataKey="overdue_tasks" name="Overdue" fill={CHART_COLORS.danger} radius={[0, 3, 3, 0]} isAnimationActive={false} />
              </BarChart>
            </ResponsiveContainer>
          </ChartPanel>
        </div>
      )}

      {people.length > 0 && (
        <Panel className="mt-4 overflow-x-auto">
          <PanelHeader title="Team detail" />
          <table className="w-full min-w-[560px] text-left text-[12.5px]">
            <thead className="text-[11px] font-semibold uppercase tracking-[0.05em] text-fg-faint">
              <tr>
                <th scope="col" className="px-4 py-2">Person</th>
                <th scope="col" className="px-3 py-2 text-right">Assigned</th>
                <th scope="col" className="px-3 py-2 text-right">High priority</th>
                <th scope="col" className="px-3 py-2 text-right">Overdue</th>
                <th scope="col" className="px-4 py-2 text-right">Completion</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line-subtle">
              {people.map((w) => (
                <tr key={w.user_id} className="hover:bg-surface-2/60">
                  <td className="px-4 py-2.5">
                    <span className="text-fg">{w.display_name}</span>
                    <span className="ml-2 text-[11px] capitalize text-fg-faint">{w.role}</span>
                  </td>
                  <td className="num px-3 py-2.5 text-right">{w.assigned_tasks}</td>
                  <td className="num px-3 py-2.5 text-right">{w.high_priority_tasks}</td>
                  <td className={`num px-3 py-2.5 text-right ${w.overdue_tasks ? "font-semibold text-danger" : ""}`}>{w.overdue_tasks}</td>
                  <td className="num px-4 py-2.5 text-right">{percent(w.completion_rate)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
      )}
    </div>
  );
}
