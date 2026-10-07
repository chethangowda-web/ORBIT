"use client";

import React, { useState } from "react";
import { useAuth } from "@/lib/auth";
import { Bot, Sparkles, Loader2, KeyRound } from "lucide-react";

export default function LoginPage() {
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) {
      setError("Please fill in both email and password.");
      return;
    }
    setIsSubmitting(true);
    setError(null);
    try {
      await login(email, password);
    } catch (err: any) {
      setError(err.message || "Failed to sign in. Verify your credentials.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const fillQuickAccount = (demoEmail: string) => {
    setEmail(demoEmail);
    setPassword("password123");
  };

  return (
    <div className="min-h-screen w-full flex items-center justify-center p-4 bg-[#090d16] relative overflow-hidden">
      {/* Background glow effects */}
      <div className="absolute top-1/4 -left-32 w-96 h-96 bg-indigo-600/15 rounded-full blur-[128px] pointer-events-none" />
      <div className="absolute bottom-1/4 -right-32 w-96 h-96 bg-cyan-500/15 rounded-full blur-[128px] pointer-events-none" />

      <div className="w-full max-w-md glass-panel rounded-2xl p-8 relative z-10 shadow-2xl border border-slate-800">
        {/* Brand Header */}
        <div className="flex flex-col items-center text-center mb-8">
          <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-indigo-600 to-cyan-400 flex items-center justify-center shadow-lg shadow-indigo-500/30 mb-4">
            <Bot className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-2xl font-extrabold text-white tracking-tight flex items-center gap-2">
            <span>ORBIT</span>
            <span className="text-xs px-2 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 font-medium">
              v1.0
            </span>
          </h1>
          <p className="text-xs text-slate-400 mt-1 max-w-xs">
            Multi-Agent Autonomous Task Management & Google Chat Swarm
          </p>
        </div>

        {error && (
          <div className="mb-5 p-3 rounded-xl bg-rose-950/40 border border-rose-500/30 text-rose-300 text-xs">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1.5">
              Work Email
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@orbit.dev"
              className="w-full px-3.5 py-2.5 rounded-xl bg-slate-900 border border-slate-800 text-slate-100 placeholder-slate-500 text-sm focus:outline-none focus:border-indigo-500 transition-colors"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1.5">
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              className="w-full px-3.5 py-2.5 rounded-xl bg-slate-900 border border-slate-800 text-slate-100 placeholder-slate-500 text-sm focus:outline-none focus:border-indigo-500 transition-colors"
            />
          </div>

          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full mt-2 py-2.5 px-4 rounded-xl bg-gradient-to-r from-indigo-600 to-indigo-500 hover:from-indigo-500 hover:to-indigo-400 text-white text-sm font-semibold shadow-lg shadow-indigo-600/30 transition-all hover:scale-[1.01] active:scale-[0.99] flex items-center justify-center gap-2 disabled:opacity-50"
          >
            {isSubmitting ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Sparkles className="w-4 h-4" />
            )}
            <span>Sign In to Dashboard</span>
          </button>
        </form>

        {/* Quick Demo Logins */}
        <div className="mt-8 pt-6 border-t border-slate-800/80">
          <div className="flex items-center gap-2 mb-3 text-xs font-semibold text-slate-400">
            <KeyRound className="w-3.5 h-3.5 text-indigo-400" />
            <span>1-Click Test Credentials:</span>
          </div>
          <div className="grid grid-cols-3 gap-2">
            <button
              type="button"
              onClick={() => fillQuickAccount("admin@orbit.dev")}
              className="px-2 py-1.5 rounded-lg bg-slate-900 border border-slate-800 hover:border-indigo-500/50 text-[11px] text-slate-300 hover:text-white transition-all text-center"
            >
              <span className="font-semibold block">Admin</span>
              <span className="text-[9px] text-slate-500">System</span>
            </button>
            <button
              type="button"
              onClick={() => fillQuickAccount("sarah@orbit.dev")}
              className="px-2 py-1.5 rounded-lg bg-slate-900 border border-slate-800 hover:border-indigo-500/50 text-[11px] text-slate-300 hover:text-white transition-all text-center"
            >
              <span className="font-semibold block">Manager</span>
              <span className="text-[9px] text-slate-500">Sarah</span>
            </button>
            <button
              type="button"
              onClick={() => fillQuickAccount("john@orbit.dev")}
              className="px-2 py-1.5 rounded-lg bg-slate-900 border border-slate-800 hover:border-indigo-500/50 text-[11px] text-slate-300 hover:text-white transition-all text-center"
            >
              <span className="font-semibold block">Employee</span>
              <span className="text-[9px] text-slate-500">John</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
