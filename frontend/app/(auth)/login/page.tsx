"use client";

import React, { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { AlertCircle, ShieldCheck, User, UserCog } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Field";
import { ApiError, apiClient } from "@/lib/api-client";
import { useAuth } from "@/lib/auth";

const DEMO_ACCOUNTS = [
  { email: "admin@orbit.dev", label: "Admin", icon: ShieldCheck },
  { email: "sarah@orbit.dev", label: "Manager", icon: UserCog },
  { email: "john@orbit.dev", label: "Employee", icon: User },
];

// Demo accounts are shown when a demo password is configured at build time
// (NEXT_PUBLIC_DEMO_PASSWORD), and always in development. Leave it unset on a real deployment:
// the value is visible to everyone who opens the page.
const DEMO_PASSWORD = process.env.NEXT_PUBLIC_DEMO_PASSWORD || (process.env.NODE_ENV !== "production" ? "password123" : "");

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const { login, status } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(params.get("expired") ? "Your session expired. Please sign in again." : null);
  const [busy, setBusy] = useState(false);
  const [waking, setWaking] = useState(false);

  // The free hosting plan puts the server to sleep when idle. Wake it as soon as the page opens, so by the
  // time someone has typed a password it is ready, and say so if it takes a while.
  useEffect(() => {
    const notice = window.setTimeout(() => setWaking(true), 2500);
    apiClient
      .get("/health", { timeout: 90_000 })
      .catch(() => undefined)
      .finally(() => {
        window.clearTimeout(notice);
        setWaking(false);
      });
    return () => window.clearTimeout(notice);
  }, []);

  useEffect(() => {
    if (status === "authenticated") router.replace("/");
  }, [status, router]);

  const signIn = async (nextEmail: string, nextPassword: string) => {
    setBusy(true);
    setError(null);
    // A request that never reached the server (status 0) usually means it was still waking up: try again.
    for (let attempt = 1; attempt <= 3; attempt += 1) {
      try {
        await login(nextEmail, nextPassword);
        return;
      } catch (e) {
        const unreachable = e instanceof ApiError && e.status === 0;
        if (unreachable && attempt < 3) {
          setWaking(true);
          continue;
        }
        setWaking(false);
        setError(e instanceof Error ? e.message : "Could not sign in.");
        setBusy(false);
        return;
      }
    }
  };

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim() || !password) {
      setError("Enter your email and password.");
      return;
    }
    void signIn(email.trim(), password);
  };

  return (
    <>
      <h1 className="text-lg font-semibold text-fg">Welcome back</h1>
      <p className="mb-5 mt-1 text-[13px] text-fg-muted">Sign in to your workspace.</p>

      {waking && !error && (
        <p role="status" className="mb-4 rounded-control border border-line bg-surface-2 p-3 text-xs text-fg-muted">
          Waking up the ORBIT server. After a quiet spell the first sign-in can take up to a minute.
        </p>
      )}

      {error && (
        <div role="alert" className="mb-4 flex items-start gap-2 rounded-control border border-danger/30 bg-danger/10 p-3 text-xs text-fg">
          <AlertCircle className="mt-px h-4 w-4 shrink-0 text-danger" aria-hidden />
          <span>{error}</span>
        </div>
      )}

      <form onSubmit={submit} noValidate className="space-y-3.5">
        <Input label="Email" type="email" autoComplete="username" value={email} placeholder="you@company.com" onChange={(e) => setEmail(e.target.value)} />
        <Input label="Password" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} />
        <Button type="submit" variant="primary" className="h-10 w-full text-sm" loading={busy}>
          Sign in
        </Button>
      </form>

      {DEMO_PASSWORD && (
        <div className="mt-6" data-testid="demo-accounts">
          <div className="mb-3 flex items-center gap-3 text-[11px] uppercase tracking-wider text-fg-faint">
            <span className="h-px flex-1 bg-line" />
            Try a demo account
            <span className="h-px flex-1 bg-line" />
          </div>
          <div className="grid grid-cols-3 gap-2">
            {DEMO_ACCOUNTS.map(({ email: demoEmail, label, icon: Icon }) => (
              <button
                key={demoEmail}
                type="button"
                disabled={busy}
                onClick={() => void signIn(demoEmail, DEMO_PASSWORD)}
                className="flex flex-col items-center gap-1 rounded-control border border-line bg-surface-2 px-2 py-2.5 transition-colors hover:border-accent/60 hover:bg-surface-3 disabled:opacity-50"
              >
                <Icon className="h-4 w-4 text-accent" aria-hidden />
                <span className="text-xs font-medium text-fg">{label}</span>
                <span className="w-full truncate text-center text-[10px] text-fg-faint">{demoEmail}</span>
              </button>
            ))}
          </div>
          <p className="mt-3 text-center text-[11px] text-fg-faint">
            Password for all demo accounts: <span className="num text-fg-muted">{DEMO_PASSWORD}</span>
          </p>
        </div>
      )}
    </>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginForm />
    </Suspense>
  );
}
