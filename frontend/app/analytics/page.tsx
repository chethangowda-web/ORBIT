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
  REVIEW: "#3b82f6",
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
      <div className="flex-1 flex items-center justify-center min-h-screen text-slate-400 text-xs">
        <div className="inline-block w-5 h-5 border-2 border-blue-500 border-t-transparent rounded-full animate-spin mr-2.5"></div>
        <span>Loading database analytics...</span>
      </div>
    );
  }

  // Format Status Pie Data
  const statusData = stats?.by_status
    ? Object.entries(stats.by_status).map(([key, val]) => ({
        name: key.replace("_", " "),
        value: val,
        color: STATUS_COLORS[key] || "#3b82f6",
      }))
    : [];

  // Format Priority Bar Data
  const priorityData = stats?.by_priority
    ? Object.entries(stats.by_priority).map(([key, val]) => ({
        name: key,
        tasks: val,
        color: PRIORITY_COLORS[key] || "#3b82f6",
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
      <Navbar title="Analytics & Database Metrics" />

      <div className="p-6 space-y-6 max-w-7xl mx-auto w-full">
        {/* Top KPI Summary Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="bg-slate-900 border border-slate-800 rounded-lg p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-semibold text-slate-400">Completion Rate</p>
                <h3 className="text-2xl font-bold text-emerald-400 mt-1">
                  {completionRate}%
                </h3>
              </div>
              <div className="w-10 h-10 rounded-md bg-emerald-950/40 border border-emerald-800/50 flex items-center justify-center text-emerald-400">
                <TrendingUp className="w-5 h-5" />
              </div>
            </div>
            <p className="text-[11px] text-slate-500 mt-2">
              {completed} of {total} tasks completed
            </p>
          </div>

          <div className="bg-slate-900 border border-slate-800 rounded-lg p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-semibold text-slate-400">In-Progress Tasks</p>
                <h3 className="text-2xl font-bold text-sky-400 mt-1">
                  {stats?.in_progress_tasks || 0}
                </h3>
              </div>
              <div className="w-10 h-10 rounded-md bg-sky-950/40 border border-sky-800/50 flex items-center justify-center text-sky-400">
                <Clock className="w-5 h-5" />
              </div>
            </div>
            <p className="text-[11px] text-slate-500 mt-2">Active tasks currently being worked on</p>
          </div>

          <div className="bg-slate-900 border border-slate-800 rounded-lg p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-semibold text-slate-400">Assigned Team Members</p>
                <h3 className="text-2xl font-bold text-blue-400 mt-1">
                  {workload.length}
                </h3>
              </div>
              <div className="w-10 h-10 rounded-md bg-blue-950/40 border border-blue-800/50 flex items-center justify-center text-blue-400">
                <Users className="w-5 h-5" />
              </div>
            </div>
            <p className="text-[11px] text-slate-500 mt-2">Contributors with assigned tasks</p>
          </div>
        </div>

        {/* Charts Row 1: Donut & Priority */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Status Breakdown */}
          <div className="bg-slate-900 border border-slate-800 rounded-lg p-5">
            <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider mb-4 flex items-center gap-2">
              <CheckCircle className="w-4 h-4 text-emerald-400" />
              <span>Task Status Breakdown</span>
            </h3>
            {statusData.length === 0 ? (
              <div className="h-64 flex items-center justify-center text-xs text-slate-500 border border-dashed border-slate-800 rounded-md">
                No task status data available in database
              </div>
            ) : (
              <div className="h-64 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={statusData}
                      cx="50%"
                      cy="50%"
                      innerRadius={55}
                      outerRadius={75}
                      paddingAngle={4}
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
                        borderRadius: "6px",
                        fontSize: "12px",
                      }}
                    />
                    <Legend />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>

          {/* Priority Breakdown */}
          <div className="bg-slate-900 border border-slate-800 rounded-lg p-5">
            <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider mb-4 flex items-center gap-2">
              <BarChart3 className="w-4 h-4 text-amber-400" />
              <span>Tasks by Priority Level</span>
            </h3>
            {priorityData.length === 0 ? (
              <div className="h-64 flex items-center justify-center text-xs text-slate-500 border border-dashed border-slate-800 rounded-md">
                No task priority data available in database
              </div>
            ) : (
              <div className="h-64 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={priorityData}>
                    <XAxis dataKey="name" stroke="#64748b" fontSize={11} />
                    <YAxis stroke="#64748b" fontSize={11} />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: "#0f172a",
                        borderColor: "#1e293b",
                        borderRadius: "6px",
                        fontSize: "12px",
                      }}
                    />
                    <Bar dataKey="tasks" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>
        </div>

        {/* Charts Row 2: Team Workload */}
        <div className="bg-slate-900 border border-slate-800 rounded-lg p-5">
          <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider mb-4 flex items-center gap-2">
            <Users className="w-4 h-4 text-blue-400" />
            <span>Team Workload Distribution (PostgreSQL)</span>
          </h3>
          {workloadData.length === 0 ? (
            <div className="h-64 flex items-center justify-center text-xs text-slate-500 border border-dashed border-slate-800 rounded-md">
              No team workload records found
            </div>
          ) : (
            <div className="h-72 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={workloadData} layout="vertical">
                  <XAxis type="number" stroke="#64748b" fontSize={11} />
                  <YAxis dataKey="name" type="category" stroke="#64748b" fontSize={11} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#0f172a",
                      borderColor: "#1e293b",
                      borderRadius: "6px",
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
          )}
        </div>
      </div>
    </div>
  );
}
