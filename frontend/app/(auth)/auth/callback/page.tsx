"use client";

import React, { Suspense, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { AlertCircle, CheckCircle2, KeyRound, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Field";
import { api, ApiError } from "@/lib/api-client";
import { useAuth } from "@/lib/auth";

type Phase = "loading" | "linking" | "error" | "success";

function CallbackContent() {
  const router = useRouter();
  const params = useSearchParams();
  const { setSession } = useAuth();

  const [phase, setPhase] = useState<Phase>("loading");
  const [message, setMessage] = useState<string | null>(null);
  const [link, setLink] = useState<{ token: string; email: string } | null>(null);
  const [password, setPassword] = useState("");
  const [linking, setLinking] = useState(false);
  const [linkError, setLinkError] = useState<string | null>(null);

  // The authorization code is single-use; React strict mode runs effects twice in dev.
  const exchanged = useRef(false);

  useEffect(() => {
    if (exchanged.current) return;
    exchanged.current = true;

    const code = params.get("code");
    const state = params.get("state");
    const oauthError = params.get("error");

    if (oauthError) {
      setPhase("error");
      setMessage(`Google sign-in was not completed (${oauthError}).`);
      return;
    }
    if (!code || !state) {
      setPhase("error");
      setMessage("The sign-in response is missing its code. Start again from the login page.");
      return;
    }

    api.auth
      .googleCallback(code, state)
      .then((result) => {
        setPhase("success");
        setSession(result);
      })
      .catch((error: unknown) => {
        if (error instanceof ApiError && error.status === 409 && error.meta?.code === "ACCOUNT_LINK_REQUIRED") {
          setLink({ token: String(error.meta.link_token), email: String(error.meta.email) });
          setPhase("linking");
          return;
        }
        setPhase("error");
        setMessage(error instanceof Error ? error.message : "Google sign-in failed.");
      });
  }, [params, setSession]);

  const submitLink = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!link || !password) {
      setLinkError("Enter your existing ORBIT password.");
      return;
    }
    setLinking(true);
    setLinkError(null);
    try {
      const result = await api.auth.googleLink(link.token, password);
      setPhase("success");
      setSession(result);
    } catch (error) {
      setLinkError(error instanceof Error ? error.message : "Could not link the account.");
    } finally {
      setLinking(false);
    }
  };

  if (phase === "loading" || phase === "success") {
    return (
      <div className="flex flex-col items-center gap-3 py-6 text-center" role="status">
        {phase === "loading" ? <Loader2 className="h-6 w-6 animate-spin text-accent" aria-hidden /> : <CheckCircle2 className="h-6 w-6 text-ok" aria-hidden />}
        <p className="text-[13px] font-medium text-fg">{phase === "loading" ? "Verifying your Google account" : "Signed in"}</p>
        <p className="text-xs text-fg-muted">{phase === "loading" ? "This takes a moment." : "Opening your workspace."}</p>
      </div>
    );
  }

  if (phase === "linking" && link) {
    return (
      <form onSubmit={submitLink} noValidate className="space-y-3.5">
        <div className="flex items-start gap-2 rounded-control border border-warn/30 bg-warn/10 p-3 text-xs text-fg">
          <KeyRound className="mt-px h-4 w-4 shrink-0 text-warn" aria-hidden />
          <p>
            An ORBIT account already exists for <strong>{link.email}</strong>. Enter its password once to link your Google account.
          </p>
        </div>
        <Input label="ORBIT password" type="password" autoComplete="current-password" data-autofocus autoFocus value={password} error={linkError} onChange={(e) => setPassword(e.target.value)} />
        <Button type="submit" variant="primary" className="w-full" loading={linking}>
          Link and continue
        </Button>
        <Button variant="ghost" className="w-full" onClick={() => router.replace("/login")}>
          Cancel
        </Button>
      </form>
    );
  }

  return (
    <div className="space-y-4">
      <div role="alert" className="flex items-start gap-2 rounded-control border border-danger/30 bg-danger/10 p-3 text-xs text-fg">
        <AlertCircle className="mt-px h-4 w-4 shrink-0 text-danger" aria-hidden />
        <div>
          <p className="font-medium">Sign-in failed</p>
          <p className="mt-0.5 text-fg-muted">{message}</p>
        </div>
      </div>
      <Button className="w-full" onClick={() => router.replace("/login")}>
        Back to sign in
      </Button>
    </div>
  );
}

export default function CallbackPage() {
  return (
    <Suspense fallback={null}>
      <CallbackContent />
    </Suspense>
  );
}
