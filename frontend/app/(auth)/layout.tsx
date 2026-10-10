import React from "react";
import { Orbit } from "lucide-react";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center px-4 py-10">
      <div className="mb-6 flex items-center gap-2.5">
        <span className="flex h-9 w-9 items-center justify-center rounded-control bg-accent-strong text-white">
          <Orbit className="h-5 w-5" aria-hidden />
        </span>
        <div>
          <p className="text-base font-semibold leading-tight text-fg">ORBIT</p>
          <p className="text-[11px] leading-tight text-fg-faint">Multi-agent task management</p>
        </div>
      </div>
      <div className="w-full max-w-sm rounded-modal border border-line bg-surface-1 p-6">{children}</div>
    </main>
  );
}
