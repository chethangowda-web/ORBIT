"use client";

import React from "react";
import {
  AlertTriangle,
  ArrowDown,
  ArrowRight,
  CalendarClock,
  CheckCircle2,
  Clock,
  Lightbulb,
  ListChecks,
  MessageSquare,
  Network,
  ShieldCheck,
  Wrench,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/cn";
import { formatMs } from "@/lib/format";
import {
  AGENT_ROLE,
  agentName,
  classifierLabel,
  normalizeSteps,
  outcomeOf,
  toolLabel,
  type RunLike,
} from "@/lib/workflow";

export const AGENT_ICON: Record<string, LucideIcon> = {
  supervisor: Network,
  task_agent: ListChecks,
  planner_agent: CalendarClock,
  recommendation_agent: Lightbulb,
  review_agent: ShieldCheck,
};

const TONE = {
  accent: "bg-accent/15 text-accent",
  ok: "bg-ok/15 text-ok",
  warn: "bg-warn/15 text-warn",
  danger: "bg-danger/15 text-danger",
  neutral: "bg-surface-3 text-fg-muted",
} as const;

function Stage({
  icon: Icon,
  tone,
  title,
  subtitle,
  ms,
  children,
}: {
  icon: LucideIcon;
  tone: keyof typeof TONE;
  title: string;
  subtitle?: React.ReactNode;
  ms?: number | null;
  children?: React.ReactNode;
}) {
  return (
    <div className="h-full rounded-control border border-line bg-surface-2 p-2.5">
      <div className="flex items-start gap-2">
        <span className={cn("flex h-6 w-6 shrink-0 items-center justify-center rounded-control", TONE[tone])}>
          <Icon className="h-3.5 w-3.5" aria-hidden />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-xs font-semibold text-fg">{title}</p>
          {subtitle && <p className="mt-0.5 text-[11px] leading-snug text-fg-muted">{subtitle}</p>}
        </div>
        {ms != null && ms > 0 && <span className="num shrink-0 text-[10px] text-fg-faint">{formatMs(ms)}</span>}
      </div>
      {children}
    </div>
  );
}

const intentLabel = (intent: string) => toolLabel(intent.toLowerCase());

/**
 * One request, drawn as the path it took: your message, the Supervisor's decision, the specialist
 * agent with the tools it called (numbered, in order), and the outcome.
 */
export function WorkflowDiagram({
  run,
  request,
  orientation = "vertical",
}: {
  run: RunLike;
  request?: string;
  orientation?: "vertical" | "horizontal";
}) {
  const steps = normalizeSteps(run);
  const outcome = outcomeOf(run);
  const horizontal = orientation === "horizontal";

  const items: { key: string; node: React.ReactNode }[] = [
    {
      key: "request",
      node: (
        <Stage icon={MessageSquare} tone="neutral" title="Your request" subtitle={request ? <span className="line-clamp-3 break-words">&ldquo;{request}&rdquo;</span> : "Sent from Chat or the dashboard"} />
      ),
    },
  ];

  steps.forEach((step, index) => {
    const Icon = AGENT_ICON[step.node] ?? Network;
    if (step.node === "supervisor") {
      const pct = step.confidence != null ? ` (${Math.round(step.confidence * 100)}%)` : "";
      items.push({
        key: `step-${index}`,
        node: (
          <Stage
            icon={Icon}
            tone="accent"
            title={agentName(step.node)}
            ms={step.duration_ms}
            subtitle={
              step.intent ? (
                <>
                  Understood: <span className="font-medium text-fg">{intentLabel(step.intent)}</span>
                  {pct}
                </>
              ) : (
                AGENT_ROLE.supervisor
              )
            }
          >
            <p className="mt-1.5 text-[10px] text-fg-faint">Decided by {classifierLabel(step.classifier)}</p>
          </Stage>
        ),
      });
      return;
    }

    const tools = step.tools ?? [];
    items.push({
      key: `step-${index}`,
      node: (
        <Stage icon={Icon} tone="accent" title={agentName(step.node)} ms={step.duration_ms} subtitle={AGENT_ROLE[step.node]}>
          {tools.length > 0 ? (
            <ol className="mt-2 space-y-1" aria-label="Tools used, in order">
              {tools.map((tool, i) => (
                <li key={`${tool}-${i}`} className="flex items-center gap-1.5 rounded-control bg-surface-1 px-1.5 py-1 text-[11px] text-fg-muted" title={tool}>
                  <span className="num flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-surface-3 text-[9px] text-fg-faint">{i + 1}</span>
                  <Wrench className="h-3 w-3 shrink-0 text-fg-faint" aria-hidden />
                  <span className="truncate">{toolLabel(tool)}</span>
                </li>
              ))}
            </ol>
          ) : (
            <p className="mt-1.5 text-[10px] text-fg-faint">{step.awaiting_confirmation ? "Asked for your approval first" : "Answered without looking anything up"}</p>
          )}
          {tools.length > 0 && step.awaiting_confirmation && <p className="mt-1.5 text-[10px] text-warn">Asked for your approval</p>}
        </Stage>
      ),
    });
  });

  items.push({
    key: "reply",
    node: (
      <Stage
        icon={outcome.tone === "ok" ? CheckCircle2 : outcome.tone === "warn" ? Clock : AlertTriangle}
        tone={outcome.tone}
        title={outcome.label}
        subtitle={run.total_duration_ms ? `Total ${formatMs(run.total_duration_ms)}` : undefined}
      >
        {run.error_message && <p className="mt-1.5 break-words text-[10px] text-danger">{run.error_message}</p>}
      </Stage>
    ),
  });

  return (
    <ol aria-label="Agent workflow" className={cn("flex flex-col gap-1", horizontal && "lg:flex-row lg:items-stretch lg:gap-1.5")}>
      {items.map((item, i) => (
        <React.Fragment key={item.key}>
          {i > 0 && (
            <li aria-hidden className="flex items-center justify-center text-fg-faint">
              {horizontal ? (
                <>
                  <ArrowDown className="h-3.5 w-3.5 lg:hidden" />
                  <ArrowRight className="hidden h-3.5 w-3.5 lg:block" />
                </>
              ) : (
                <ArrowDown className="h-3.5 w-3.5" />
              )}
            </li>
          )}
          <li className={cn(horizontal && "lg:min-w-0 lg:flex-1")}>{item.node}</li>
        </React.Fragment>
      ))}
    </ol>
  );
}
