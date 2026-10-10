"use client";

import React, { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api-client";
import { Bot, Loader2, AlertCircle, KeyRound, CheckCircle2 } from "lucide-react";

function CallbackContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { setSession } = useAuth();

  const [status, setStatus] = useState<"loading" | "linking" | "error" | "success">("loading");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Account linking state
  const [linkToken, setLinkToken] = useState<string | null>(null);
  const [linkEmail, setLinkEmail] = useState<string | null>(null);
  const [linkPassword, setLinkPassword] = useState("");
  const [isLinking, setIsLinking] = useState(false);
  const [linkError, setLinkError] = useState<string | null>(null);

  useEffect(() => {
    const code = searchParams.get("code");
    const state = searchParams.get("state");
    const oauthError = searchParams.get("error");

    if (oauthError) {
      setStatus("error");
      setErrorMessage(`Google authentication failed: ${oauthError}`);
      return;
    }

    if (!code || !state) {
      setStatus("error");
      setErrorMessage("Missing authorization code or state parameter.");
      return;
    }

    const exchangeCode = async () => {
      try {
        const data = await api.auth.googleCallback(code, state);
        setStatus("success");
        setSession(data.access_token, data.user);
      } catch (err: any) {
        // Check for 409 Account Link Required
        const detail = err.response?.data?.detail;
        if (detail?.code === "ACCOUNT_LINK_REQUIRED") {
          setStatus("linking");
          setLinkToken(detail.link_token);
          setLinkEmail(detail.email);
        } else {
          setStatus("error");
          setErrorMessage(
            err.message || "Failed to complete Google authentication. Please try again."
          );
        }
      }
    };

    exchangeCode();
  }, [searchParams, setSession]);

  const handleLinkAccount = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!linkToken || !linkPassword) {
      setLinkError("Please enter your existing password to verify ownership.");
      return;
    }

    setIsLinking(true);
    setLinkError(null);

    try {
      const data = await api.auth.googleLink(linkToken, linkPassword);
      setStatus("success");
      setSession(data.access_token, data.user);
    } catch (err: any) {
      setLinkError(err.message || "Invalid password. Could not link account.");
    } finally {
      setIsLinking(false);
    }
  };

  return (
    <div className="w-full max-w-md bg-slate-900 rounded-lg p-7 relative z-10 border border-slate-800 shadow-xl">
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
          Authenticating with Google Identity Services
        </p>
      </div>

      {status === "loading" && (
        <div className="py-8 flex flex-col items-center justify-center text-center space-y-3">
          <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
          <p className="text-sm font-medium text-slate-200">Verifying security token...</p>
          <p className="text-xs text-slate-400">Validating OAuth tokens and permissions</p>
        </div>
      )}

      {status === "success" && (
        <div className="py-8 flex flex-col items-center justify-center text-center space-y-3">
          <CheckCircle2 className="w-8 h-8 text-emerald-400" />
          <p className="text-sm font-medium text-slate-200">Authentication Verified!</p>
          <p className="text-xs text-slate-400">Redirecting to ORBIT workspace...</p>
        </div>
      )}

      {status === "error" && (
        <div className="space-y-4">
          <div className="p-3.5 rounded-md bg-rose-950/60 border border-rose-500/40 text-rose-300 text-xs flex items-start gap-2.5">
            <AlertCircle className="w-4 h-4 text-rose-400 flex-shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold mb-0.5">Authentication Failed</p>
              <p className="text-slate-300">{errorMessage}</p>
            </div>
          </div>

          <button
            onClick={() => router.push("/login")}
            className="w-full py-2 px-4 rounded-md bg-slate-800 hover:bg-slate-700 text-white text-xs font-semibold transition-colors"
          >
            Return to Login
          </button>
        </div>
      )}

      {status === "linking" && (
        <div className="space-y-4">
          <div className="p-3.5 rounded-md bg-amber-950/60 border border-amber-500/40 text-amber-300 text-xs flex items-start gap-2.5">
            <KeyRound className="w-4 h-4 text-amber-400 flex-shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold mb-0.5">Verify Account Ownership</p>
              <p className="text-slate-300">
                An account already exists for <strong className="text-white">{linkEmail}</strong>.
                Enter your existing password to link Google authentication.
              </p>
            </div>
          </div>

          {linkError && (
            <div className="p-2.5 rounded-md bg-rose-950/60 border border-rose-500/40 text-rose-300 text-xs">
              {linkError}
            </div>
          )}

          <form onSubmit={handleLinkAccount} className="space-y-3">
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">
                Account Password
              </label>
              <input
                type="password"
                value={linkPassword}
                onChange={(e) => setLinkPassword(e.target.value)}
                placeholder="Enter your existing ORBIT password"
                className="w-full px-3 py-2 rounded-md bg-slate-950 border border-slate-800 text-slate-100 placeholder-slate-500 text-xs focus:outline-none focus:border-blue-500 transition-colors"
                autoFocus
              />
            </div>

            <button
              type="submit"
              disabled={isLinking}
              className="w-full py-2 px-4 rounded-md bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold transition-colors flex items-center justify-center gap-2 disabled:opacity-50"
            >
              {isLinking && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
              <span>Link Account & Continue</span>
            </button>

            <button
              type="button"
              onClick={() => router.push("/login")}
              className="w-full py-1.5 text-center text-xs text-slate-400 hover:text-slate-200 transition-colors"
            >
              Cancel
            </button>
          </form>
        </div>
      )}
    </div>
  );
}

export default function AuthCallbackPage() {
  return (
    <div className="min-h-screen w-full flex items-center justify-center p-4 bg-[#090d16] relative overflow-hidden">
      <Suspense
        fallback={
          <div className="w-full max-w-md bg-slate-900 rounded-lg p-7 border border-slate-800 text-center text-slate-300 text-xs">
            <Loader2 className="w-6 h-6 animate-spin mx-auto text-blue-500 mb-2" />
            Loading authentication handler...
          </div>
        }
      >
        <CallbackContent />
      </Suspense>
    </div>
  );
}
