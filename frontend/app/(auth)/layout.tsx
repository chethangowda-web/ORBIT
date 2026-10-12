import React from "react";
import { Orbit } from "lucide-react";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <main className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden px-4 py-10">
      {/* A soft glow behind the card; purely decorative. */}
      <div aria-hidden className="pointer-events-none absolute left-1/2 top-[-18%] h-[520px] w-[820px] -translate-x-1/2 rounded-full bg-accent/10 blur-3xl" />
      <div className="relative w-full max-w-[400px]">
        <div className="mb-7 flex items-center justify-center gap-3">
          <span className="flex h-11 w-11 items-center justify-center rounded-panel bg-accent-strong text-white shadow-lg shadow-accent/20">
            <Orbit className="h-6 w-6" aria-hidden />
          </span>
          <p className="text-2xl font-semibold tracking-tight text-fg">ORBIT</p>
        </div>
        <div className="rounded-modal border border-line bg-surface-1 p-7 shadow-2xl shadow-black/20">{children}</div>
      </div>
    </main>
  );
}
