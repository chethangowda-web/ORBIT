"use client";

import React, { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import { AgentRail } from "@/components/agent/AgentRail";
import { AgentProvider } from "@/lib/agent-context";
import { useAuth } from "@/lib/auth";
import { routeRequiresManager } from "@/lib/session";
import { CommandPalette } from "./CommandPalette";
import { MobileNav, NavRail } from "./NavRail";
import { ShellProvider } from "./ShellContext";
import { TopBar } from "./TopBar";

/** Authenticated layout: nav rail, top bar, content, and the agent rail. */
export function AppShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { status, isManager } = useAuth();
  const [paletteOpen, setPaletteOpen] = useState(false);

  useEffect(() => {
    if (status === "anonymous") router.replace("/login");
  }, [status, router]);

  // Managers-only screens bounce everyone else back to the board.
  const forbidden = status === "authenticated" && routeRequiresManager(pathname) && !isManager;
  useEffect(() => {
    if (forbidden) router.replace("/");
  }, [forbidden, router]);

  // Ctrl/Cmd+K toggles the palette from anywhere.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen((open) => !open);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  if (status !== "authenticated" || forbidden) {
    return (
      <div className="flex h-screen items-center justify-center text-fg-muted" role="status">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden />
        Loading workspace
      </div>
    );
  }

  return (
    <AgentProvider>
      <ShellProvider>
        <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded-control focus:bg-surface-3 focus:px-3 focus:py-1.5">
          Skip to content
        </a>
        <div className="flex h-screen overflow-hidden bg-bg">
          <NavRail />
          <div className="flex min-w-0 flex-1 flex-col">
            <TopBar onOpenPalette={() => setPaletteOpen(true)} />
            <main id="main" className="min-h-0 flex-1 overflow-y-auto p-4 md:p-5">
              {children}
            </main>
            <MobileNav />
          </div>
          <AgentRail />
        </div>
        <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
      </ShellProvider>
    </AgentProvider>
  );
}
