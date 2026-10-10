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
    color: "text-slate-400",
    border: "border-[#263241]",
    bg: "bg-[#151F2C]",
    icon: <ArrowDown className="w-3 h-3 text-slate-400" />,
  },
  MEDIUM: {
    label: "Medium",
    color: "text-amber-400",
    border: "border-amber-500/30",
    bg: "bg-amber-950/40",
    icon: <Minus className="w-3 h-3 text-amber-400" />,
  },
  HIGH: {
    label: "High",
    color: "text-orange-400",
    border: "border-orange-500/30",
    bg: "bg-orange-950/40",
    icon: <ArrowUp className="w-3 h-3 text-orange-400" />,
  },
  CRITICAL: {
    label: "Critical",
    color: "text-rose-400",
    border: "border-rose-500/40",
    bg: "bg-rose-950/50",
    icon: <AlertCircle className="w-3 h-3 text-rose-400" />,
  },
};

export const PriorityBadge: React.FC<PriorityBadgeProps> = ({ priority, size = "md" }) => {
  const config = priorityConfig[priority] || priorityConfig.MEDIUM;
  const sizeClasses = size === "sm" ? "px-2 py-0.5 text-[11px]" : "px-2.5 py-1 text-xs font-medium";

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-md border ${config.border} ${config.bg} ${config.color} ${sizeClasses} font-mono`}
    >
      {config.icon}
      <span>{config.label}</span>
    </span>
  );
};
