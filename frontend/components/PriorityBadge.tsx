import React from "react";
import { TaskPriority } from "@/types";
import { AlertCircle, ArrowDown, ArrowUp, Minus } from "lucide-react";

interface PriorityBadgeProps {
  priority: TaskPriority | string;
  size?: "sm" | "md";
}

const priorityConfig: Record<
  string,
  { label: string; color: string; border: string; bg: string; icon: React.ReactNode }
> = {
  LOW: {
    label: "Low",
    color: "text-slate-300",
    border: "border-slate-700/60",
    bg: "bg-slate-800/40",
    icon: <ArrowDown className="w-3 h-3 text-slate-400" />,
  },
  MEDIUM: {
    label: "Medium",
    color: "text-amber-300",
    border: "border-amber-500/30",
    bg: "bg-amber-950/40",
    icon: <Minus className="w-3 h-3 text-amber-400" />,
  },
  HIGH: {
    label: "High",
    color: "text-orange-300",
    border: "border-orange-500/30",
    bg: "bg-orange-950/40",
    icon: <ArrowUp className="w-3 h-3 text-orange-400" />,
  },
  CRITICAL: {
    label: "Critical",
    color: "text-rose-300",
    border: "border-rose-500/40",
    bg: "bg-rose-950/60",
    icon: <AlertCircle className="w-3 h-3 text-rose-400 animate-pulse" />,
  },
};

export const PriorityBadge: React.FC<PriorityBadgeProps> = ({ priority, size = "md" }) => {
  const config = priorityConfig[priority] || priorityConfig.MEDIUM;
  const sizeClasses = size === "sm" ? "px-2 py-0.5 text-xs" : "px-2.5 py-1 text-xs font-semibold";

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-md border ${config.border} ${config.bg} ${config.color} ${sizeClasses}`}
    >
      {config.icon}
      <span>{config.label}</span>
    </span>
  );
};
