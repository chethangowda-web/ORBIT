"use client";

import React, { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { useAuth } from "@/lib/auth";
import { Navbar } from "@/components/Navbar";
import {
  Bot,
  Play,
  Clock,
  CheckCircle2,
  AlertCircle,
  Calendar,
  Server,
  Loader2,
} from "lucide-react";

export default function SettingsPage() {
  const { user } = useAuth();
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  // Fetch scheduler status
  const { data: schedulerStatus, refetch } = useQuery({
    queryKey: ["schedulerStatus"],
    queryFn: () => api.admin.status(),
    retry: false,
  });

  // Briefing trigger mutation
  const briefingMutation = useMutation({
    mutationFn: () => api.admin.triggerBriefing(true),
    onSuccess: (data) => {
      setActionMessage(`✅ Daily briefing triggered successfully! Processed: ${data.processed}, Sent: ${data.sent}`);
      refetch();
    },
    onError: (err: any) => {
      setActionMessage(`❌ Error: ${err.message}`);
    },
  });

  // Overdue alerts trigger mutation
  const overdueMutation = useMutation({
    mutationFn: () => api.admin.triggerOverdue(true),
    onSuccess: (data) => {
      setActionMessage(`✅ Overdue alerts triggered! Flagged: ${data.tasks_flagged}, Sent: ${data.sent}`);
      refetch();
    },
    onError: (err: any) => {
      setActionMessage(`❌ Error: ${err.message}`);
    },
  });

  // Weekly summary trigger mutation
  const weeklyMutation = useMutation({
    mutationFn: () => api.admin.triggerWeekly(true),
    onSuccess: (data) => {
      setActionMessage(`✅ Weekly summary triggered! Sent: ${data.sent}`);
      refetch();
    },
    onError: (err: any) => {
      setActionMessage(`❌ Error: ${err.message}`);
    },
  });

  return (
    <div className="flex-1 flex flex-col min-h-screen">
      <Navbar title="Settings & Autonomous Scheduler" />

      <div className="p-6 max-w-5xl mx-auto w-full space-y-6">
        {/* User Profile Card */}
        <div className="glass-panel rounded-2xl p-6 border border-slate-800">
          <div className="flex items-center gap-3 mb-6 pb-4 border-b border-slate-800">
            <div className="w-12 h-12 rounded-2xl bg-gradient-to-tr from-indigo-500 to-purple-600 flex items-center justify-center text-white font-bold text-lg uppercase shadow-md">
              {user?.display_name?.charAt(0) || "U"}
            </div>
            <div>
              <h2 className="text-base font-bold text-white">{user?.display_name}</h2>
              <p className="text-xs text-slate-400">{user?.email}</p>
            </div>
            <span className="ml-auto text-xs px-2.5 py-1 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 font-semibold uppercase">
              {user?.role}
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
            <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800">
              <span className="text-slate-500 block mb-1">Timezone</span>
              <span className="text-slate-200 font-medium">{user?.timezone || "Asia/Kolkata"}</span>
            </div>
            <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800">
              <span className="text-slate-500 block mb-1">Google Chat ID</span>
              <span className="text-slate-200 font-medium font-mono text-[11px]">
                {user?.google_id || "Unlinked (simulate mode)"}
              </span>
            </div>
            <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800">
              <span className="text-slate-500 block mb-1">Account Status</span>
              <span className="text-emerald-400 font-medium flex items-center gap-1">
                <CheckCircle2 className="w-3.5 h-3.5" />
                Active
              </span>
            </div>
          </div>
        </div>

        {/* Autonomous Scheduler Controls */}
        <div className="glass-panel rounded-2xl p-6 border border-slate-800">
          <div className="flex items-center justify-between mb-4 pb-4 border-b border-slate-800">
            <div className="flex items-center gap-2.5">
              <Server className="w-5 h-5 text-indigo-400" />
              <div>
                <h3 className="text-sm font-bold text-white">Autonomous Background Scheduler</h3>
                <p className="text-xs text-slate-400">
                  APScheduler engine managing proactive briefings and automated alerts.
                </p>
              </div>
            </div>

            {schedulerStatus && (
              <span
                className={`text-xs px-2.5 py-1 rounded-full font-semibold border ${
                  schedulerStatus.running
                    ? "bg-emerald-950/40 text-emerald-400 border-emerald-500/30"
                    : "bg-amber-950/40 text-amber-400 border-amber-500/30"
                }`}
              >
                {schedulerStatus.running ? "Scheduler Running" : "Scheduler Idle"}
              </span>
            )}
          </div>

          {actionMessage && (
            <div className="mb-4 p-3 rounded-xl bg-indigo-950/40 border border-indigo-500/30 text-xs text-indigo-200">
              {actionMessage}
            </div>
          )}

          {/* Manual Trigger Buttons */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-6">
            <button
              onClick={() => briefingMutation.mutate()}
              disabled={briefingMutation.isPending}
              className="flex items-center justify-center gap-2 p-3 rounded-xl bg-slate-900 hover:bg-slate-850 border border-slate-800 hover:border-indigo-500/40 text-slate-200 text-xs font-semibold transition-all"
            >
              {briefingMutation.isPending ? (
                <Loader2 className="w-4 h-4 animate-spin text-indigo-400" />
              ) : (
                <Play className="w-3.5 h-3.5 text-indigo-400" />
              )}
              <span>Trigger Morning Briefing</span>
            </button>

            <button
              onClick={() => overdueMutation.mutate()}
              disabled={overdueMutation.isPending}
              className="flex items-center justify-center gap-2 p-3 rounded-xl bg-slate-900 hover:bg-slate-850 border border-slate-800 hover:border-rose-500/40 text-slate-200 text-xs font-semibold transition-all"
            >
              {overdueMutation.isPending ? (
                <Loader2 className="w-4 h-4 animate-spin text-rose-400" />
              ) : (
                <AlertCircle className="w-3.5 h-3.5 text-rose-400" />
              )}
              <span>Trigger Overdue Alerts</span>
            </button>

            <button
              onClick={() => weeklyMutation.mutate()}
              disabled={weeklyMutation.isPending}
              className="flex items-center justify-center gap-2 p-3 rounded-xl bg-slate-900 hover:bg-slate-850 border border-slate-800 hover:border-emerald-500/40 text-slate-200 text-xs font-semibold transition-all"
            >
              {weeklyMutation.isPending ? (
                <Loader2 className="w-4 h-4 animate-spin text-emerald-400" />
              ) : (
                <Calendar className="w-3.5 h-3.5 text-emerald-400" />
              )}
              <span>Trigger Weekly Summary</span>
            </button>
          </div>

          {/* Active Scheduled Jobs List */}
          <div>
            <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3">
              Configured Cron Jobs
            </h4>

            {schedulerStatus?.jobs && schedulerStatus.jobs.length > 0 ? (
              <div className="space-y-2">
                {schedulerStatus.jobs.map((job) => (
                  <div
                    key={job.id}
                    className="flex items-center justify-between p-3 rounded-xl bg-slate-950/60 border border-slate-800 text-xs"
                  >
                    <div>
                      <span className="font-semibold text-slate-200">{job.name}</span>
                      <span className="text-slate-500 ml-2 font-mono text-[11px]">
                        ID: {job.id}
                      </span>
                    </div>

                    <div className="flex items-center gap-2 text-slate-400">
                      <Clock className="w-3.5 h-3.5 text-slate-500" />
                      <span>Next Run: {job.next_run_time ? new Date(job.next_run_time).toLocaleString() : "Pending"}</span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-slate-500">
                Jobs registered and triggered automatically on API startup.
              </p>
            )}
          </div>
        </div>

        {/* Multi-Agent Architecture Overview */}
        <div className="glass-panel rounded-2xl p-6 border border-slate-800">
          <div className="flex items-center gap-2 mb-3">
            <Bot className="w-5 h-5 text-cyan-400" />
            <h3 className="text-sm font-bold text-white">ORBIT Multi-Agent Architecture</h3>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs mt-3">
            <div className="p-3 rounded-xl bg-slate-950/50 border border-slate-850">
              <span className="font-semibold text-indigo-300 block mb-1">Supervisor Agent</span>
              <p className="text-slate-400 text-[11px]">
                Deterministic intent classification routing to specialists.
              </p>
            </div>
            <div className="p-3 rounded-xl bg-slate-950/50 border border-slate-850">
              <span className="font-semibold text-sky-300 block mb-1">Specialist Swarm</span>
              <p className="text-slate-400 text-[11px]">
                Task CRUD, Planner, Recommendation, and Review HITL agents.
              </p>
            </div>
            <div className="p-3 rounded-xl bg-slate-950/50 border border-slate-850">
              <span className="font-semibold text-emerald-300 block mb-1">Omnichannel Delivery</span>
              <p className="text-slate-400 text-[11px]">
                Bi-directional Google Chat webhooks + Next.js web application.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
