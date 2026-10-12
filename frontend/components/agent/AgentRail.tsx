"use client";

import React, { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Bot, ChevronDown, PanelRightClose, RotateCcw, Send, ShieldAlert, Sparkles } from "lucide-react";
import { Button, IconButton } from "@/components/ui/Button";
import { RunStatusBadge } from "@/components/ui/Badge";
import { Skeleton } from "@/components/ui/Primitives";
import { useAgent, type ChatMessage } from "@/lib/agent-context";
import { WorkflowDiagram } from "./WorkflowDiagram";
import { ChatText } from "@/lib/chat-text";
import { AGENT_LABEL } from "@/lib/constants";
import { cn } from "@/lib/cn";
import { formatMs, timeAgo } from "@/lib/format";
import { useTraces } from "@/lib/hooks";
import { agentName, intentLabel, normalizeSteps } from "@/lib/workflow";
import type { AgentExecutionTrace, ChatExecutionMetadata } from "@/types";

function TraceDetails({ metadata, request, defaultOpen }: { metadata: ChatExecutionMetadata; request?: string; defaultOpen: boolean }) {
  const steps = normalizeSteps(metadata);
  const handler = steps.filter((s) => s.node !== "supervisor").map((s) => agentName(s.node)).join(" > ");
  return (
    <details className="group mt-2 border-t border-line-subtle pt-1.5 text-[10px]" open={defaultOpen}>
      <summary className="flex cursor-pointer list-none items-center justify-between text-fg-faint hover:text-fg-muted">
        <span className="flex items-center gap-1">
          <Sparkles className="h-3 w-3" aria-hidden />
          <span>How ORBIT handled this{handler ? ` · ${handler}` : ""}</span>
        </span>
        <span className="num flex items-center gap-1">
          {formatMs(metadata.total_duration_ms)}
          <ChevronDown className="h-3 w-3 transition-transform group-open:rotate-180" aria-hidden />
        </span>
      </summary>
      <div className="mt-2">
        <WorkflowDiagram run={metadata} request={request} />
      </div>
    </details>
  );
}

function Message({ message, request, latest, disabled, onAsk }: { message: ChatMessage; request?: string; latest: boolean; disabled: boolean; onAsk: (text: string, confirmed?: boolean) => void }) {
  const mine = message.sender === "user";
  return (
    <div className={cn("flex flex-col", mine ? "items-end" : "items-start")}>
      <div
        className={cn(
          "max-w-[92%] rounded-panel px-3 py-2 text-[12.5px] leading-relaxed",
          mine
            ? "bg-accent-strong text-white"
            : message.isError
              ? "border border-danger/40 bg-danger/5 text-fg"
              : "border border-line bg-surface-2 text-fg-muted",
        )}
      >
        <ChatText text={message.text} />

        {message.needsConfirmation && (
          <div className="mt-2.5 rounded-control border border-warn/30 bg-warn/5 p-2.5">
            <p className="mb-2 flex items-center gap-1.5 text-xs font-semibold text-warn">
              <ShieldAlert className="h-3.5 w-3.5" aria-hidden />
              Approval required
            </p>
            <div className="flex gap-2">
              <Button size="sm" variant="primary" disabled={disabled || message.resolved} onClick={() => onAsk("yes", true)}>
                Confirm
              </Button>
              <Button size="sm" disabled={disabled || message.resolved} onClick={() => onAsk("cancel")}>
                Cancel
              </Button>
            </div>
          </div>
        )}

        {message.referencedTasks && message.referencedTasks.length > 0 && (
          <ul className="mt-2 space-y-1 border-t border-line-subtle pt-2">
            {message.referencedTasks.map((t) => (
              <li key={t.id}>
                <Link
                  href={`/tasks/${t.id}`}
                  className="flex items-center justify-between gap-2 rounded-control border border-line bg-surface-1 px-2 py-1.5 hover:border-fg-faint"
                >
                  <span className="truncate text-xs text-fg">{t.title}</span>
                  {t.priority && <span className="num shrink-0 text-[10px] uppercase text-fg-faint">{t.priority}</span>}
                </Link>
              </li>
            ))}
          </ul>
        )}

        {!mine && message.metadata && <TraceDetails metadata={message.metadata} request={request} defaultOpen={latest} />}
      </div>

      {!mine && message.suggestedActions && message.suggestedActions.length > 0 && !message.needsConfirmation && (
        <div className="mt-1.5 flex max-w-[92%] flex-wrap gap-1">
          {message.suggestedActions.map((action) => (
            <button
              key={action}
              type="button"
              disabled={disabled}
              onClick={() => onAsk(action)}
              className="rounded-control border border-line bg-surface-1 px-2 py-1 text-[11px] text-fg-muted transition-colors hover:border-accent/50 hover:text-fg disabled:opacity-50"
            >
              {action}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function ChatPanel() {
  const { messages, sending, ask, reset } = useAgent();
  const [draft, setDraft] = useState("");
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, sending]);

  const send = (e: React.FormEvent) => {
    e.preventDefault();
    const text = draft;
    setDraft("");
    void ask(text);
  };

  return (
    <>
      <div className="flex-1 space-y-3 overflow-y-auto px-3 py-3" aria-live="polite">
        {messages.map((m, i) => {
          const previous = messages[i - 1];
          const request = previous && previous.sender === "user" ? previous.text : undefined;
          const lastWithRun = messages.map((x) => Boolean(x.metadata)).lastIndexOf(true);
          return (
            <Message
              key={m.id}
              message={m}
              request={request}
              latest={i === lastWithRun}
              disabled={sending}
              onAsk={(text, confirmed) => void ask(text, { confirmed })}
            />
          );
        })}
        {sending && (
          <div className="rounded-control border border-line bg-surface-2 p-2.5 text-xs text-fg-muted" role="status">
            <p className="flex items-center gap-2 font-medium text-fg">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-info" aria-hidden />
              ORBIT is working on it
            </p>
            <p className="mt-1 text-[11px]">Reading your request, then the right helper will check your tasks and answer.</p>
          </div>
        )}
        <div ref={endRef} />
      </div>
      <form onSubmit={send} className="border-t border-line p-2.5">
        <div className="flex items-center gap-2">
          <label htmlFor="agent-input" className="sr-only">
            Message ORBIT
          </label>
          <input
            id="agent-input"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            disabled={sending}
            maxLength={1000}
            autoComplete="off"
            placeholder="Ask ORBIT to plan, find or change tasks"
            className="h-8 flex-1 rounded-control border border-line bg-surface-2 px-3 text-[13px] text-fg placeholder:text-fg-faint focus:border-accent focus:outline-none disabled:opacity-50"
          />
          <IconButton label="Send message" type="submit" disabled={sending || !draft.trim()} className="bg-accent-strong text-white hover:bg-accent hover:text-white">
            <Send className="h-3.5 w-3.5" />
          </IconButton>
        </div>
        <button type="button" onClick={reset} className="mt-1.5 flex items-center gap-1 text-[11px] text-fg-faint transition-colors hover:text-fg-muted">
          <RotateCcw className="h-3 w-3" aria-hidden /> New conversation
        </button>
      </form>
    </>
  );
}

function RunRow({ run }: { run: AgentExecutionTrace }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <li className="border-b border-line-subtle last:border-0">
      <button
        type="button"
        aria-expanded={expanded}
        onClick={() => setExpanded((v) => !v)}
        className="w-full px-3 py-2.5 text-left transition-colors hover:bg-surface-2/60"
      >
        <div className="flex items-center justify-between gap-2">
          <span className="truncate text-xs font-medium text-fg">{intentLabel(run.intent)}</span>
          <RunStatusBadge status={run.status} />
        </div>
        <div className="mt-1 flex items-center justify-between text-[11px] text-fg-faint">
          <span className="truncate">{run.agents_invoked.map((a) => AGENT_LABEL[a] ?? a).join(" > ") || "Coordinator"}</span>
          <span className="num shrink-0">
            {formatMs(run.total_duration_ms)} / {timeAgo(run.started_at)}
          </span>
        </div>
      </button>
      {expanded && (
        <div className="px-3 pb-3">
          <WorkflowDiagram run={run} />
        </div>
      )}
    </li>
  );
}

function RunsPanel() {
  const { data, isLoading, isError } = useTraces(15);
  if (isLoading)
    return (
      <div className="space-y-3 p-3">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-10 w-full" />
        ))}
      </div>
    );
  if (isError) return <p className="p-4 text-xs text-fg-muted">Could not load recent runs.</p>;
  if (!data || data.items.length === 0)
    return <p className="p-4 text-xs text-fg-muted">Nothing yet. Ask ORBIT something to see how it was handled.</p>;
  return (
    <div className="flex-1 overflow-y-auto">
      <ul>{data.items.map((run) => <RunRow key={run.id} run={run} />)}</ul>
      <Link href="/traces" className="block px-3 py-3 text-center text-[11px] text-accent hover:underline">
        Open ORBIT activity
      </Link>
    </div>
  );
}

export function AgentRail() {
  const { open, setOpen } = useAgent();
  const [tab, setTab] = useState<"chat" | "runs">("chat");
  if (!open) return null;

  return (
    <>
      <div className="fixed inset-0 z-30 bg-black/50 lg:hidden" onClick={() => setOpen(false)} aria-hidden />
      <aside
        aria-label="Ask ORBIT"
        className="fixed inset-y-0 right-0 z-40 flex w-full max-w-sm flex-col border-l border-line bg-surface-1 animate-slide-in-right lg:static lg:z-auto lg:w-[320px] lg:max-w-none lg:animate-none"
      >
        <header className="flex items-center justify-between border-b border-line px-3 py-2">
          <div className="flex items-center gap-2">
            <span className="flex h-7 w-7 items-center justify-center rounded-control border border-line bg-surface-2 text-accent">
              <Bot className="h-4 w-4" aria-hidden />
            </span>
            <div role="tablist" aria-label="Ask ORBIT sections" className="flex gap-0.5">
              {(["chat", "runs"] as const).map((id) => (
                <button
                  key={id}
                  role="tab"
                  type="button"
                  aria-selected={tab === id}
                  onClick={() => setTab(id)}
                  className={cn(
                    "rounded-control px-2.5 py-1 text-xs font-medium capitalize transition-colors",
                    tab === id ? "bg-surface-3 text-fg" : "text-fg-muted hover:text-fg",
                  )}
                >
                  {id === "chat" ? "Ask" : "History"}
                </button>
              ))}
            </div>
          </div>
          <IconButton label="Close Ask ORBIT" size="sm" onClick={() => setOpen(false)}>
            <PanelRightClose className="h-4 w-4" />
          </IconButton>
        </header>
        {tab === "chat" ? <ChatPanel /> : <RunsPanel />}
      </aside>
    </>
  );
}
