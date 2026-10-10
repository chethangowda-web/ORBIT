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
    <aside className="w-64 flex-shrink-0 h-screen sticky top-0 bg-[#0C121A] border-r border-[#263241] flex flex-col justify-between p-4 z-40">
      <div>
        {/* Brand Header */}
        <div className="flex items-center gap-3 px-3 py-4 mb-6 border-b border-[#1C2633] pb-4">
          <div className="flex items-center justify-center w-9 h-9 rounded-md bg-[#111821] border border-[#263241] shadow-sm">
            <Bot className="w-5 h-5 text-blue-400" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-base font-bold tracking-tight text-white">ORBIT</span>
              <span className="text-[10px] font-mono uppercase tracking-wider px-1.5 py-0.5 rounded bg-blue-950/60 text-blue-400 border border-blue-800/60">
                Ops
              </span>
            </div>
            <p className="text-[11px] text-slate-400">Multi-Agent System</p>
          </div>
        </div>

        {/* Navigation Links */}
        <nav className="space-y-1">
          {navItems.map((item) => {
            const isActive = pathname === item.href;
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-3 px-3 py-2 rounded-md text-xs font-medium transition-colors ${
                  isActive
                    ? "bg-[#151F2C] text-[#E5EAF1] border border-[#263241]"
                    : "text-slate-400 hover:text-slate-200 hover:bg-[#111821] border border-transparent"
                }`}
              >
                <Icon className={`w-4 h-4 ${isActive ? "text-blue-400" : "text-slate-400"}`} />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>

        {/* Engine Status Banner */}
        <div className="mt-8 mx-1 p-3 rounded-md bg-[#111821] border border-[#263241] text-xs">
          <div className="flex items-center gap-2 mb-1 text-slate-300 font-semibold text-[11px]">
            <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
            <span>LangGraph Engine</span>
          </div>
          <p className="text-slate-400 text-[11px] leading-relaxed">
            Autonomous supervisors and Google Chat webhook orchestration online.
          </p>
        </div>
      </div>

      {/* User Info & Logout */}
      {user && (
        <div className="border-t border-[#1C2633] pt-3 px-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5 truncate">
              <div className="w-7 h-7 rounded-md bg-[#151F2C] border border-[#263241] flex items-center justify-center text-blue-400 text-xs font-bold uppercase">
                {user.display_name?.charAt(0) || "U"}
              </div>
              <div className="truncate">
                <p className="text-xs font-medium text-slate-200 truncate">{user.display_name}</p>
                <p className="text-[10px] text-slate-400 truncate capitalize">{user.role}</p>
              </div>
            </div>
            <button
              onClick={logout}
              title="Sign Out"
              className="p-1.5 rounded-md text-slate-400 hover:text-rose-400 hover:bg-rose-950/30 transition-colors"
            >
              <LogOut className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      )}
    </aside>
  );
};
