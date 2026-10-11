"use client";

import React, { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { AlertCircle, KeyRound } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Field";
import { useAuth } from "@/lib/auth";

const DEMO_ACCOUNTS = [
  { email: "admin@orbit.dev", label: "Admin" },
  { email: "sarah@orbit.dev", label: "Manager" },
  { email: "john@orbit.dev", label: "Employee" },
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
  const [busy, setBusy] = useState<"password" | null>(null);

  useEffect(() => {
    if (status === "authenticated") router.replace("/");
  }, [status, router]);

  const signIn = async (nextEmail: string, nextPassword: string) => {
    setBusy("password");
    setError(null);
    try {
      await login(nextEmail, nextPassword);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not sign in.");
      setBusy(null);
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
      <h1 className="mb-4 text-sm font-semibold text-fg">Sign in</h1>

      {error && (
        <div role="alert" className="mb-4 flex items-start gap-2 rounded-control border border-danger/30 bg-danger/10 p-3 text-xs text-fg">
          <AlertCircle className="mt-px h-4 w-4 shrink-0 text-danger" aria-hidden />
          <span>{error}</span>
        </div>
      )}

      <form onSubmit={submit} noValidate className="space-y-3">
        <Input label="Work email" type="email" autoComplete="username" value={email} placeholder="you@company.com" onChange={(e) => setEmail(e.target.value)} />
        <Input label="Password" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} />
        <Button type="submit" variant="primary" className="w-full" loading={busy === "password"}>
          Sign in
        </Button>
      </form>

      {DEMO_PASSWORD && (
        <div className="mt-5 border-t border-line-subtle pt-4" data-testid="demo-accounts">
          <p className="mb-2 flex items-center gap-1.5 text-[11px] text-fg-faint">
            <KeyRound className="h-3 w-3" aria-hidden /> Demo accounts
          </p>
          <div className="grid grid-cols-3 gap-2">
            {DEMO_ACCOUNTS.map((a) => (
              <Button key={a.email} size="sm" disabled={busy !== null} onClick={() => void signIn(a.email, DEMO_PASSWORD)}>
                {a.label}
              </Button>
            ))}
          </div>
          <dl className="mt-3 space-y-0.5 text-[11px] text-fg-muted">
            {DEMO_ACCOUNTS.map((a) => (
              <div key={a.email} className="flex justify-between gap-3">
                <dt>{a.label}</dt>
                <dd className="num text-fg">{a.email}</dd>
              </div>
            ))}
            <div className="flex justify-between gap-3 border-t border-line-subtle pt-1">
              <dt>Password</dt>
              <dd className="num text-fg">{DEMO_PASSWORD}</dd>
            </div>
          </dl>
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
