"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Activity, BarChart3, LayoutDashboard, ListChecks, Orbit, Settings2 } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/cn";

interface NavItem {
  href: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  managerOnly?: boolean;
}

export const NAV_ITEMS: NavItem[] = [
  { href: "/", label: "Board", icon: LayoutDashboard },
  { href: "/tasks", label: "Tasks", icon: ListChecks },
  { href: "/insights", label: "Insights", icon: BarChart3, managerOnly: true },
  { href: "/traces", label: "Agent workflow", icon: Activity },
  { href: "/admin", label: "Admin", icon: Settings2, managerOnly: true },
];

export function isActivePath(pathname: string, href: string): boolean {
  return href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`);
}

function useVisibleItems() {
  const { isManager } = useAuth();
  return NAV_ITEMS.filter((item) => !item.managerOnly || isManager);
}

/** Desktop icon rail. */
export function NavRail() {
  const pathname = usePathname();
  const items = useVisibleItems();
  return (
    <nav aria-label="Primary" className="hidden w-14 shrink-0 flex-col items-center border-r border-line bg-surface-1 py-3 md:flex">
      <Link href="/" aria-label="ORBIT home" className="mb-4 flex h-9 w-9 items-center justify-center rounded-control bg-accent-strong text-white">
        <Orbit className="h-5 w-5" aria-hidden />
      </Link>
      <ul className="flex flex-1 flex-col items-center gap-1">
        {items.map((item) => {
          const active = isActivePath(pathname, item.href);
          const Icon = item.icon;
          return (
            <li key={item.href} className="group relative">
              <Link
                href={item.href}
                aria-label={item.label}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex h-9 w-9 items-center justify-center rounded-control border transition-colors",
                  active ? "border-line bg-surface-3 text-accent" : "border-transparent text-fg-muted hover:bg-surface-2 hover:text-fg",
                )}
              >
                <Icon className="h-[18px] w-[18px]" />
              </Link>
              <span className="pointer-events-none absolute left-full top-1/2 z-50 ml-2 -translate-y-1/2 whitespace-nowrap rounded-control border border-line bg-surface-3 px-2 py-1 text-xs text-fg opacity-0 transition-opacity group-hover:opacity-100 group-focus-within:opacity-100">
                {item.label}
              </span>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

/** Bottom bar for small screens. */
export function MobileNav() {
  const pathname = usePathname();
  const items = useVisibleItems();
  return (
    <nav aria-label="Primary" className="flex shrink-0 border-t border-line bg-surface-1 md:hidden">
      {items.map((item) => {
        const active = isActivePath(pathname, item.href);
        const Icon = item.icon;
        return (
          <Link
            key={item.href}
            href={item.href}
            aria-current={active ? "page" : undefined}
            className={cn("flex flex-1 flex-col items-center gap-0.5 py-2 text-[10px]", active ? "text-accent" : "text-fg-muted")}
          >
            <Icon className="h-[18px] w-[18px]" />
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
