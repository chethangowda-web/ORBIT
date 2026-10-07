import React from "react";
import { TaskStatus } from "@/types";
import { CheckCircle2, Clock, Eye, Circle } from "lucide-react";

interface StatusBadgeProps {
  status: TaskStatus | string;
  size?: "sm" | "md";
}

const statusConfig: Record<
  string,
  { label: string; color: string; border: string; bg: string; icon: React.ReactNode }
> = {
  TODO: {
    label: "To Do",
    color: "text-slate-300",
    border: "border-slate-700/60",
    bg: "bg-slate-800/60",
    icon: <Circle className="w-3 h-3 text-slate-400" />,
  },
  IN_PROGRESS: {
    label: "In Progress",
    color: "text-sky-300",
    border: "border-sky-500/30",
    bg: "bg-sky-950/40",
    icon: <Clock className="w-3 h-3 text-sky-400 animate-pulse" />,
  },
  REVIEW: {
    label: "Under Review",
    color: "text-purple-300",
    border: "border-purple-500/30",
    bg: "bg-purple-950/40",
    icon: <Eye className="w-3 h-3 text-purple-400" />,
  },
  DONE: {
    label: "Completed",
    color: "text-emerald-300",
    border: "border-emerald-500/30",
    bg: "bg-emerald-950/40",
    icon: <CheckCircle2 className="w-3 h-3 text-emerald-400" />,
  },
};

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, size = "md" }) => {
  const config = statusConfig[status] || statusConfig.TODO;
  const sizeClasses = size === "sm" ? "px-2 py-0.5 text-xs" : "px-2.5 py-1 text-xs font-medium";

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border ${config.border} ${config.bg} ${config.color} ${sizeClasses}`}
    >
      {config.icon}
      <span>{config.label}</span>
    </span>
  );
};
