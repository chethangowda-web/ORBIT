"use client";

import React, { useState } from "react";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api-client";
import { Bot, Loader2, KeyRound, AlertCircle } from "lucide-react";

export default function LoginPage() {
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isGoogleLoading, setIsGoogleLoading] = useState(false);

  const handleGoogleSignIn = async () => {
    setIsGoogleLoading(true);
    setError(null);
    try {
      const response = await api.auth.googleUrl();
      if (response?.authorization_url) {
        window.location.href = response.authorization_url;
      } else {
        throw new Error("Unable to retrieve Google authorization URL.");
      }
    } catch (err: any) {
      setError(
        err.message ||
          "Google Sign-In is not configured or temporarily unavailable. Use password login."
      );
      setIsGoogleLoading(false);
    }
  };

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

  const isDevMode = process.env.NODE_ENV !== "production";

  return (
    <div className="min-h-screen w-full flex items-center justify-center p-4 bg-[#090d16] relative overflow-hidden">
      <div className="w-full max-w-md bg-slate-900 rounded-lg p-7 relative z-10 border border-slate-800 shadow-xl">
        {/* Brand Header */}
        <div className="flex flex-col items-center text-center mb-6">
          <div className="w-11 h-11 rounded-md bg-slate-800 border border-slate-700/80 flex items-center justify-center text-blue-400 mb-3 shadow-inner">
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
          <div className="mb-4 p-3 rounded-md bg-rose-950/60 border border-rose-500/40 text-rose-300 text-xs flex items-start gap-2">
            <AlertCircle className="w-4 h-4 text-rose-400 flex-shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        {/* Primary Action: Continue with Google */}
        <button
          type="button"
          onClick={handleGoogleSignIn}
          disabled={isGoogleLoading || isSubmitting}
          className="w-full py-2.5 px-4 rounded-md bg-white hover:bg-slate-100 text-slate-900 text-xs font-semibold transition-all duration-200 flex items-center justify-center gap-3 shadow-md hover:shadow-lg disabled:opacity-50"
        >
          {isGoogleLoading ? (
            <Loader2 className="w-4 h-4 animate-spin text-slate-700" />
          ) : (
            <svg className="w-4 h-4" viewBox="0 0 24 24">
              <path
                fill="#4285F4"
                d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
              />
              <path
                fill="#34A853"
                d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
              />
              <path
                fill="#FBBC05"
                d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
              />
              <path
                fill="#EA4335"
                d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
              />
            </svg>
          )}
          <span>Continue with Google</span>
        </button>

        {/* Divider */}
        <div className="relative my-4 flex items-center justify-center">
          <div className="w-full border-t border-slate-800" />
          <span className="absolute bg-slate-900 px-3 text-[11px] font-medium text-slate-500 uppercase tracking-wider">
            or password
          </span>
        </div>

        {/* Secondary: Email & Password */}
        <form onSubmit={handleSubmit} className="space-y-3">
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
            disabled={isSubmitting || isGoogleLoading}
            className="w-full mt-2 py-2 px-4 rounded-md bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold transition-colors flex items-center justify-center gap-2 disabled:opacity-50"
          >
            {isSubmitting && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
            <span>Sign In with Password</span>
          </button>
        </form>

        {/* Development Only Demo Logins */}
        {isDevMode && (
          <div className="mt-5 pt-4 border-t border-slate-800">
            <div className="flex items-center gap-1.5 mb-2 text-xs font-medium text-slate-400">
              <KeyRound className="w-3.5 h-3.5 text-blue-400" />
              <span>Dev Demo Accounts (Local Only):</span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
              <button
                type="button"
                disabled={isSubmitting || isGoogleLoading}
                onClick={() => fillQuickAccount("admin@orbit.dev")}
                className="px-2.5 py-1.5 rounded-md bg-slate-950 hover:bg-slate-850 border border-slate-800 hover:border-slate-700 text-xs text-slate-300 hover:text-white transition-colors text-left"
              >
                <span className="font-semibold block text-slate-200">Admin</span>
                <span className="text-[10px] text-slate-500">System Admin</span>
              </button>
              <button
                type="button"
                disabled={isSubmitting || isGoogleLoading}
                onClick={() => fillQuickAccount("sarah@orbit.dev")}
                className="px-2.5 py-1.5 rounded-md bg-slate-950 hover:bg-slate-850 border border-slate-800 hover:border-slate-700 text-xs text-slate-300 hover:text-white transition-colors text-left"
              >
                <span className="font-semibold block text-slate-200">Sarah</span>
                <span className="text-[10px] text-slate-500">Manager</span>
              </button>
              <button
                type="button"
                disabled={isSubmitting || isGoogleLoading}
                onClick={() => fillQuickAccount("john@orbit.dev")}
                className="px-2.5 py-1.5 rounded-md bg-slate-950 hover:bg-slate-850 border border-slate-800 hover:border-slate-700 text-xs text-slate-300 hover:text-white transition-colors text-left"
              >
                <span className="font-semibold block text-slate-200">John</span>
                <span className="text-[10px] text-slate-500">Employee</span>
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
