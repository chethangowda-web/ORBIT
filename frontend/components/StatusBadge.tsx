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
    border: "border-[#263241]",
    bg: "bg-[#151F2C]",
    icon: <Circle className="w-3 h-3 text-slate-400" />,
  },
  IN_PROGRESS: {
    label: "In Progress",
    color: "text-blue-400",
    border: "border-blue-500/30",
    bg: "bg-blue-950/40",
    icon: <Clock className="w-3 h-3 text-blue-400" />,
  },
  REVIEW: {
    label: "Under Review",
    color: "text-amber-400",
    border: "border-amber-500/30",
    bg: "bg-amber-950/40",
    icon: <Eye className="w-3 h-3 text-amber-400" />,
  },
  DONE: {
    label: "Completed",
    color: "text-emerald-400",
    border: "border-emerald-500/30",
    bg: "bg-emerald-950/40",
    icon: <CheckCircle2 className="w-3 h-3 text-emerald-400" />,
  },
};

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, size = "md" }) => {
  const config = statusConfig[status] || statusConfig.TODO;
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
