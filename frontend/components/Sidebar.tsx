"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth";
import {
  LayoutDashboard,
  CheckSquare,
  BarChart3,
  Settings,
  LogOut,
  Bot,
  Sparkles,
} from "lucide-react";

export const Sidebar: React.FC = () => {
  const pathname = usePathname();
  const { user, logout } = useAuth();

  const navItems = [
    { href: "/", label: "Dashboard", icon: LayoutDashboard },
    { href: "/tasks", label: "Tasks", icon: CheckSquare },
    { href: "/analytics", label: "Analytics", icon: BarChart3 },
    { href: "/settings", label: "Settings & System", icon: Settings },
  ];

  if (pathname === "/login") {
    return null;
  }

  return (
    <aside className="w-64 flex-shrink-0 h-screen sticky top-0 bg-slate-950/80 border-r border-slate-800/80 backdrop-blur-xl flex flex-col justify-between p-4 z-40">
      <div>
        {/* Brand Header */}
        <div className="flex items-center gap-3 px-3 py-4 mb-6">
          <div className="relative flex items-center justify-center w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-600 via-indigo-500 to-cyan-400 shadow-lg shadow-indigo-500/20">
            <Bot className="w-6 h-6 text-white" />
            <span className="absolute -top-1 -right-1 flex h-3 w-3">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-3 w-3 bg-cyan-500"></span>
            </span>
          </div>
          <div>
            <div className="flex items-center gap-1.5">
              <span className="text-xl font-bold tracking-tight text-white">ORBIT</span>
              <span className="text-[10px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                AI Agent
              </span>
            </div>
            <p className="text-xs text-slate-400">Task Management</p>
          </div>
        </div>

        {/* Navigation Links */}
        <nav className="space-y-1.5">
          {navItems.map((item) => {
            const isActive = pathname === item.href;
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-sm font-medium transition-all duration-200 ${
                  isActive
                    ? "bg-indigo-600/15 text-indigo-400 border border-indigo-500/30 shadow-sm shadow-indigo-500/10"
                    : "text-slate-400 hover:text-slate-200 hover:bg-slate-900/60 border border-transparent"
                }`}
              >
                <Icon className={`w-4 h-4 ${isActive ? "text-indigo-400" : "text-slate-400"}`} />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>

        {/* Multi-Agent Live Banner */}
        <div className="mt-8 mx-1 p-3.5 rounded-xl bg-slate-900/70 border border-slate-800 text-xs text-slate-300 relative overflow-hidden">
          <div className="flex items-center gap-2 mb-1.5 text-indigo-400 font-semibold">
            <Sparkles className="w-3.5 h-3.5 animate-spin" />
            <span>Multi-Agent Swarm</span>
          </div>
          <p className="text-slate-400 text-[11px] leading-relaxed">
            LangGraph agents orchestrating tasks via Google Chat & autonomous cron triggers.
          </p>
        </div>
      </div>

      {/* User Info & Logout */}
      {user && (
        <div className="border-t border-slate-800/80 pt-4 px-2">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2.5 truncate">
              <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-indigo-500 to-purple-600 flex items-center justify-center text-white text-xs font-bold uppercase shadow-sm">
                {user.display_name?.charAt(0) || "U"}
              </div>
              <div className="truncate">
                <p className="text-xs font-semibold text-slate-200 truncate">{user.display_name}</p>
                <p className="text-[10px] text-slate-400 truncate capitalize">{user.role}</p>
              </div>
            </div>
            <button
              onClick={logout}
              title="Sign Out"
              className="p-1.5 rounded-lg text-slate-400 hover:text-rose-400 hover:bg-rose-950/30 transition-colors"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
    </aside>
  );
};
