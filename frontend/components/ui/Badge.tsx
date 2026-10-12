import React from "react";
import { AlertOctagon, ArrowDown, ArrowUp, CheckCircle2, Circle, CircleDashed, Clock, Eye, Minus, XCircle } from "lucide-react";
import { cn } from "@/lib/cn";
import { PRIORITY_LABEL, PRIORITY_TONE, STATUS_LABEL, STATUS_TONE } from "@/lib/constants";
import type { TaskPriority, TaskStatus } from "@/types";

export type Tone = "muted" | "info" | "warn" | "ok" | "faint" | "danger" | "high" | "accent";

const TONE_CLASSES: Record<Tone, string> = {
  muted: "text-fg-muted bg-fg-muted/10 border-fg-muted/25",
  faint: "text-fg-faint bg-fg-faint/10 border-fg-faint/25",
  info: "text-info bg-info/10 border-info/30",
  warn: "text-warn bg-warn/10 border-warn/30",
  ok: "text-ok bg-ok/10 border-ok/30",
  danger: "text-danger bg-danger/10 border-danger/30",
  high: "text-high bg-high/10 border-high/30",
  accent: "text-accent bg-accent/10 border-accent/30",
};

export function Badge({
  tone = "muted",
  className,
  children,
}: {
  tone?: Tone;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <span
      className={cn(
        "inline-flex h-5 items-center gap-1 whitespace-nowrap rounded-control border px-1.5 text-[11px] font-medium",
        TONE_CLASSES[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

const STATUS_ICON: Record<TaskStatus, React.ReactNode> = {
  TODO: <Circle className="h-3 w-3" aria-hidden />,
  IN_PROGRESS: <Clock className="h-3 w-3" aria-hidden />,
  REVIEW: <Eye className="h-3 w-3" aria-hidden />,
  DONE: <CheckCircle2 className="h-3 w-3" aria-hidden />,
  CANCELLED: <XCircle className="h-3 w-3" aria-hidden />,
};

export function StatusBadge({ status }: { status: TaskStatus | string }) {
  const known = status in STATUS_LABEL;
  const key = (known ? status : "TODO") as TaskStatus;
  return (
    <Badge tone={STATUS_TONE[key]}>
      {STATUS_ICON[key]}
      {known ? STATUS_LABEL[key] : status}
    </Badge>
  );
}

const PRIORITY_ICON: Record<TaskPriority, React.ReactNode> = {
  CRITICAL: <AlertOctagon className="h-3 w-3" aria-hidden />,
  HIGH: <ArrowUp className="h-3 w-3" aria-hidden />,
  MEDIUM: <Minus className="h-3 w-3" aria-hidden />,
  LOW: <ArrowDown className="h-3 w-3" aria-hidden />,
};

export function PriorityBadge({ priority }: { priority: TaskPriority | string }) {
  const known = priority in PRIORITY_LABEL;
  const key = (known ? priority : "MEDIUM") as TaskPriority;
  return (
    <Badge tone={PRIORITY_TONE[key]}>
      {PRIORITY_ICON[key]}
      {known ? PRIORITY_LABEL[key] : priority}
    </Badge>
  );
}

const RUN_STATUS_LABEL: Record<string, string> = {
  SUCCESS: "Done",
  NEEDS_CONFIRMATION: "Needs your approval",
  TIMEOUT: "Took too long",
  FAILURE: "Didn't work",
};

export function RunStatusBadge({ status }: { status: string }) {
  const tone: Tone =
    status === "SUCCESS" ? "ok" : status === "NEEDS_CONFIRMATION" ? "warn" : status === "TIMEOUT" ? "high" : "danger";
  const icon = status === "SUCCESS" ? <CheckCircle2 className="h-3 w-3" aria-hidden /> : <CircleDashed className="h-3 w-3" aria-hidden />;
  return (
    <Badge tone={tone}>
      {icon}
      {RUN_STATUS_LABEL[status] ?? status.charAt(0) + status.slice(1).toLowerCase()}
    </Badge>
  );
}
