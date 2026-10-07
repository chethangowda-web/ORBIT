"use client";

import React from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { Navbar } from "@/components/Navbar";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
} from "recharts";
import { BarChart3, TrendingUp, Users, CheckCircle, Clock } from "lucide-react";

const STATUS_COLORS: Record<string, string> = {
  TODO: "#94a3b8",
  IN_PROGRESS: "#38bdf8",
  REVIEW: "#a855f7",
  DONE: "#10b981",
};

const PRIORITY_COLORS: Record<string, string> = {
  LOW: "#64748b",
  MEDIUM: "#f59e0b",
  HIGH: "#f97316",
  CRITICAL: "#f43f5e",
};

export default function AnalyticsPage() {
  const { data: stats, isLoading: isStatsLoading } = useQuery({
    queryKey: ["taskStats"],
    queryFn: () => api.analytics.stats(),
  });

  const { data: workload = [], isLoading: isWorkloadLoading } = useQuery({
    queryKey: ["teamWorkload"],
    queryFn: () => api.analytics.workload(),
  });

  if (isStatsLoading || isWorkloadLoading) {
    return (
      <div className="flex-1 flex items-center justify-center min-h-screen text-slate-400">
        <div className="inline-block w-6 h-6 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin mr-3"></div>
        Loading analytics...
      </div>
    );
  }

  // Format Status Pie Data
  const statusData = stats?.by_status
    ? Object.entries(stats.by_status).map(([key, val]) => ({
        name: key.replace("_", " "),
        value: val,
        color: STATUS_COLORS[key] || "#6366f1",
      }))
    : [];

  // Format Priority Bar Data
  const priorityData = stats?.by_priority
    ? Object.entries(stats.by_priority).map(([key, val]) => ({
        name: key,
        tasks: val,
        color: PRIORITY_COLORS[key] || "#6366f1",
      }))
    : [];

  // Workload data
  const workloadData = workload.map((w) => ({
    name: w.display_name,
    assigned: w.assigned_tasks,
    completed: w.completed_tasks,
    overdue: w.overdue_tasks,
  }));

  const total = stats?.total_tasks || 0;
  const completed = stats?.completed_tasks || 0;
  const completionRate = total > 0 ? ((completed / total) * 100).toFixed(1) : "0.0";

  return (
    <div className="flex-1 flex flex-col min-h-screen">
      <Navbar title="Analytics & Productivity" />

      <div className="p-6 space-y-6 max-w-7xl mx-auto w-full">
        {/* Top KPI Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="glass-panel rounded-2xl p-5 border border-slate-800">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-semibold text-slate-400">Completion Rate</p>
                <h3 className="text-3xl font-extrabold text-emerald-400 mt-1">
                  {completionRate}%
                </h3>
              </div>
              <div className="w-12 h-12 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
                <TrendingUp className="w-6 h-6" />
              </div>
            </div>
            <p className="text-[11px] text-slate-500 mt-2">
              {completed} of {total} total tasks resolved
            </p>
          </div>

          <div className="glass-panel rounded-2xl p-5 border border-slate-800">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-semibold text-slate-400">Active Workstreams</p>
                <h3 className="text-3xl font-extrabold text-sky-400 mt-1">
                  {stats?.in_progress_tasks || 0}
                </h3>
              </div>
              <div className="w-12 h-12 rounded-xl bg-sky-500/10 border border-sky-500/20 flex items-center justify-center text-sky-400">
                <Clock className="w-6 h-6" />
              </div>
            </div>
            <p className="text-[11px] text-slate-500 mt-2">Currently in development</p>
          </div>

          <div className="glass-panel rounded-2xl p-5 border border-slate-800">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-semibold text-slate-400">Team Contributors</p>
                <h3 className="text-3xl font-extrabold text-indigo-400 mt-1">
                  {workload.length}
                </h3>
              </div>
              <div className="w-12 h-12 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
                <Users className="w-6 h-6" />
              </div>
            </div>
            <p className="text-[11px] text-slate-500 mt-2">Collaborating across spaces</p>
          </div>
        </div>

        {/* Charts Row 1: Donut & Priority */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Status Donut */}
          <div className="glass-panel rounded-2xl p-6 border border-slate-800">
            <h3 className="text-sm font-bold text-white mb-4 flex items-center gap-2">
              <CheckCircle className="w-4 h-4 text-emerald-400" />
              <span>Status Distribution</span>
            </h3>
            <div className="h-64 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={statusData}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={80}
                    paddingAngle={5}
                    dataKey="value"
                  >
                    {statusData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#0f172a",
                      borderColor: "#1e293b",
                      borderRadius: "8px",
                      fontSize: "12px",
                    }}
                  />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Priority Breakdown */}
          <div className="glass-panel rounded-2xl p-6 border border-slate-800">
            <h3 className="text-sm font-bold text-white mb-4 flex items-center gap-2">
              <BarChart3 className="w-4 h-4 text-orange-400" />
              <span>Tasks by Priority</span>
            </h3>
            <div className="h-64 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={priorityData}>
                  <XAxis dataKey="name" stroke="#64748b" fontSize={12} />
                  <YAxis stroke="#64748b" fontSize={12} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#0f172a",
                      borderColor: "#1e293b",
                      borderRadius: "8px",
                      fontSize: "12px",
                    }}
                  />
                  <Bar dataKey="tasks" fill="#6366f1" radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>

        {/* Charts Row 2: Team Workload */}
        <div className="glass-panel rounded-2xl p-6 border border-slate-800">
          <h3 className="text-sm font-bold text-white mb-4 flex items-center gap-2">
            <Users className="w-4 h-4 text-indigo-400" />
            <span>Team Workload Distribution</span>
          </h3>
          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={workloadData} layout="vertical">
                <XAxis type="number" stroke="#64748b" fontSize={12} />
                <YAxis dataKey="name" type="category" stroke="#64748b" fontSize={12} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#0f172a",
                    borderColor: "#1e293b",
                    borderRadius: "8px",
                    fontSize: "12px",
                  }}
                />
                <Legend />
                <Bar dataKey="assigned" name="Assigned" fill="#38bdf8" radius={[0, 4, 4, 0]} />
                <Bar dataKey="completed" name="Completed" fill="#10b981" radius={[0, 4, 4, 0]} />
                <Bar dataKey="overdue" name="Overdue" fill="#f43f5e" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  );
}
