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

  const fillQuickAccount = async (demoEmail: string) => {
    setEmail(demoEmail);
    setPassword("password123");
    setIsSubmitting(true);
    setError(null);
    try {
      await login(demoEmail, "password123");
    } catch (err: any) {
      setError(err.message || "Failed to sign in. Verify your credentials.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen w-full flex items-center justify-center p-4 bg-[#090d16] relative overflow-hidden">
      <div className="w-full max-w-md bg-slate-900 rounded-lg p-7 relative z-10 border border-slate-800 shadow-xl">
        {/* Brand Header */}
        <div className="flex flex-col items-center text-center mb-6">
          <div className="w-11 h-11 rounded-md bg-slate-800 border border-slate-700/80 flex items-center justify-center text-blue-400 mb-3">
            <Bot className="w-6 h-6" />
          </div>
          <h1 className="text-xl font-bold text-slate-100 tracking-tight flex items-center gap-2">
            <span>ORBIT</span>
            <span className="text-[10px] px-1.5 py-0.2 rounded-md bg-slate-800 text-slate-300 border border-slate-700/60 font-mono">
              v1.0
            </span>
          </h1>
          <p className="text-xs text-slate-400 mt-1 max-w-xs">
            Multi-Agent Task Management & Autonomous Orchestration
          </p>
        </div>

        {error && (
          <div className="mb-4 p-3 rounded-md bg-rose-950/60 border border-rose-500/40 text-rose-300 text-xs">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-3.5">
          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1">
              Work Email
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="admin@orbit.dev"
              className="w-full px-3 py-2 rounded-md bg-slate-950 border border-slate-800 text-slate-100 placeholder-slate-500 text-xs focus:outline-none focus:border-blue-500 transition-colors"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1">
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              className="w-full px-3 py-2 rounded-md bg-slate-950 border border-slate-800 text-slate-100 placeholder-slate-500 text-xs focus:outline-none focus:border-blue-500 transition-colors"
            />
          </div>

          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full mt-2 py-2 px-4 rounded-md bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold transition-colors flex items-center justify-center gap-2 disabled:opacity-50"
          >
            {isSubmitting && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
            <span>Sign In to Dashboard</span>
          </button>
        </form>

        {/* Quick Demo Logins */}
        <div className="mt-6 pt-5 border-t border-slate-800">
          <div className="flex items-center gap-1.5 mb-2.5 text-xs font-medium text-slate-400">
            <KeyRound className="w-3.5 h-3.5 text-blue-400" />
            <span>1-Click Verified Demo Accounts:</span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
            <button
              type="button"
              disabled={isSubmitting}
              onClick={() => fillQuickAccount("admin@orbit.dev")}
              className="px-2.5 py-2 rounded-md bg-slate-950 hover:bg-slate-850 border border-slate-800 hover:border-slate-700 text-xs text-slate-300 hover:text-white transition-colors text-left"
            >
              <span className="font-semibold block text-slate-200">Admin</span>
              <span className="text-[10px] text-slate-500">System Admin</span>
            </button>
            <button
              type="button"
              disabled={isSubmitting}
              onClick={() => fillQuickAccount("sarah@orbit.dev")}
              className="px-2.5 py-2 rounded-md bg-slate-950 hover:bg-slate-850 border border-slate-800 hover:border-slate-700 text-xs text-slate-300 hover:text-white transition-colors text-left"
            >
              <span className="font-semibold block text-slate-200">Sarah</span>
              <span className="text-[10px] text-slate-500">Manager</span>
            </button>
            <button
              type="button"
              disabled={isSubmitting}
              onClick={() => fillQuickAccount("john@orbit.dev")}
              className="px-2.5 py-2 rounded-md bg-slate-950 hover:bg-slate-850 border border-slate-800 hover:border-slate-700 text-xs text-slate-300 hover:text-white transition-colors text-left"
            >
              <span className="font-semibold block text-slate-200">John Doe</span>
              <span className="text-[10px] text-slate-500">13 Tasks</span>
            </button>
          </div>
          <p className="text-[10px] text-slate-500 mt-2 text-center">
            Password: <code className="text-slate-400">password123</code> • Google Chat users authenticate via Google Chat.
          </p>
        </div>
      </div>
    </div>
  );
}
