"use client";

import React, { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Bot, LogOut, Plus, Search, UserCircle } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { ThemeCycleButton } from "@/components/ui/ThemeSwitcher";
import { Avatar, Kbd } from "@/components/ui/Primitives";
import { useAgent } from "@/lib/agent-context";
import { useAuth } from "@/lib/auth";
import { ROLE_LABEL } from "@/lib/constants";
import { cn } from "@/lib/cn";
import { useHealth } from "@/lib/hooks";
import { useLiveUpdates } from "@/lib/live";
import type { UserRole } from "@/types";
import { useShell } from "./ShellContext";

const TITLES: Record<string, string> = {
  "/": "Board",
  "/tasks": "Tasks",
  "/insights": "Insights",
  "/traces": "Agent runs",
  "/admin": "Admin",
  "/profile": "Profile",
};

export function titleFor(pathname: string): string {
  if (TITLES[pathname]) return TITLES[pathname];
  if (pathname.startsWith("/tasks/")) return "Task";
  const match = Object.keys(TITLES).find((p) => p !== "/" && pathname.startsWith(p));
  return match ? TITLES[match] : "ORBIT";
}

function HealthPill() {
  const { data, isError, isLoading } = useHealth();
  const live = useLiveUpdates();
  let tone = "bg-fg-faint";
  let label = "Checking";
  if (!isLoading) {
    if (isError || !data) {
      tone = "bg-danger";
      label = "API unreachable";
    } else if (data.database !== "connected") {
      tone = "bg-danger";
      label = "Database down";
    } else if (data.redis !== "connected") {
      tone = "bg-warn";
      label = "Cache offline";
    } else {
      tone = "bg-ok";
      label = live ? "Live" : "All systems normal";
    }
  }
  return (
    <span className="hidden items-center gap-2 rounded-control border border-line bg-surface-2 px-2.5 py-1 text-[11px] text-fg-muted lg:inline-flex" role="status">
      <span className={cn("h-1.5 w-1.5 rounded-full", tone)} aria-hidden />
      {label}
    </span>
  );
}

function UserMenu() {
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => !ref.current?.contains(e.target as Node) && setOpen(false);
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  if (!user) return null;
  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label="Account menu"
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 rounded-control p-1 transition-colors hover:bg-surface-2"
      >
        <Avatar name={user.display_name} size="md" />
      </button>
      {open && (
        <div role="menu" className="absolute right-0 top-full z-50 mt-1.5 w-56 rounded-panel border border-line bg-surface-3 p-1 shadow-xl animate-fade-in">
          <div className="border-b border-line-subtle px-3 py-2">
            <p className="truncate text-[13px] font-medium text-fg">{user.display_name}</p>
            <p className="truncate text-[11px] text-fg-muted">{user.email}</p>
            <p className="mt-1 text-[10px] uppercase tracking-wide text-fg-faint">{ROLE_LABEL[user.role as UserRole]}</p>
          </div>
          <Link role="menuitem" href="/profile" onClick={() => setOpen(false)} className="mt-1 flex items-center gap-2 rounded-control px-3 py-1.5 text-[13px] text-fg-muted hover:bg-surface-2 hover:text-fg">
            <UserCircle className="h-4 w-4" aria-hidden /> Profile
          </Link>
          <button role="menuitem" type="button" onClick={() => logout()} className="flex w-full items-center gap-2 rounded-control px-3 py-1.5 text-left text-[13px] text-fg-muted hover:bg-danger/10 hover:text-danger">
            <LogOut className="h-4 w-4" aria-hidden /> Sign out
          </button>
        </div>
      )}
    </div>
  );
}

export function TopBar({ onOpenPalette }: { onOpenPalette: () => void }) {
  const pathname = usePathname();
  const { open, setOpen } = useAgent();
  const { openNewTask } = useShell();
  return (
    <header className="flex h-12 shrink-0 items-center gap-3 border-b border-line bg-surface-1 px-4">
      <h1 className="text-[13px] font-semibold text-fg">{titleFor(pathname)}</h1>

      <button
        type="button"
        onClick={onOpenPalette}
        aria-label="Open command palette"
        className="ml-2 flex h-8 max-w-sm flex-1 items-center gap-2 rounded-control border border-line bg-surface-2 px-2.5 text-xs text-fg-faint transition-colors hover:border-fg-faint"
      >
        <Search className="h-3.5 w-3.5" aria-hidden />
        <span className="flex-1 truncate text-left">
          <span className="sm:hidden">Search</span>
          <span className="hidden sm:inline">Search or run a command</span>
        </span>
        <span className="hidden items-center gap-1 sm:flex">
          <Kbd>Ctrl</Kbd>
          <Kbd>K</Kbd>
        </span>
      </button>

      <div className="ml-auto flex items-center gap-2">
        <HealthPill />
        <ThemeCycleButton />
        <Button size="sm" variant="primary" onClick={() => openNewTask()}>
          <Plus className="h-3.5 w-3.5" aria-hidden />
          <span className="hidden sm:inline">New task</span>
          <span className="sr-only sm:hidden">New task</span>
        </Button>
        <Button size="sm" aria-pressed={open} onClick={() => setOpen(!open)}>
          <Bot className="h-3.5 w-3.5" aria-hidden />
          <span className="hidden sm:inline">Agent</span>
          <span className="sr-only sm:hidden">Toggle agent panel</span>
        </Button>
        <UserMenu />
      </div>
    </header>
  );
}
