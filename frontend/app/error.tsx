"use client";

import { useEffect } from "react";
import { AlertTriangle } from "lucide-react";

export default function GlobalError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <main className="flex min-h-screen flex-col items-center justify-center px-4 text-center">
      <AlertTriangle className="mb-2 h-6 w-6 text-danger" aria-hidden />
      <h1 className="text-lg font-semibold text-fg">Something broke on this page</h1>
      <p className="mt-1 max-w-sm text-xs text-fg-muted">
        The error has been logged in your browser console. Try again; if it keeps happening, reload the page.
        {error.digest && <span className="num block pt-1 text-fg-faint">ref {error.digest}</span>}
      </p>
      <button type="button" onClick={reset} className="mt-4 inline-flex h-8 items-center rounded-control border border-line bg-surface-2 px-3 text-[13px] font-medium text-fg hover:bg-surface-3">
        Try again
      </button>
    </main>
  );
}
