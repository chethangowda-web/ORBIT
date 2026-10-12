"use client";

import React, { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { BarChart3, Bot, CornerDownLeft, LayoutDashboard, ListChecks, Plus, Search, Settings2, Activity, UserCircle } from "lucide-react";
import { Kbd } from "@/components/ui/Primitives";
import { useFocusTrap } from "@/components/ui/Overlay";
import { useAgent } from "@/lib/agent-context";
import { useAuth } from "@/lib/auth";
import { filterCommands, moveIndex, type Command } from "@/lib/commands";
import { cn } from "@/lib/cn";
import { useTasks } from "@/lib/hooks";
import { useShell } from "./ShellContext";

function useDebounced<T>(value: T, delay = 200): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const id = window.setTimeout(() => setDebounced(value), delay);
    return () => window.clearTimeout(id);
  }, [value, delay]);
  return debounced;
}

export function CommandPalette({ open, onClose }: { open: boolean; onClose: () => void }) {
  const router = useRouter();
  const { isManager } = useAuth();
  const { ask } = useAgent();
  const { openNewTask } = useShell();
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const panelRef = useRef<HTMLDivElement>(null);
  const debouncedQuery = useDebounced(query.trim());

  useFocusTrap(panelRef, open, onClose);
  useEffect(() => {
    if (open) {
      setQuery("");
      setActive(0);
    }
  }, [open]);

  const searchActive = open && debouncedQuery.length >= 2;
  const { data: found } = useTasks(
    { q: debouncedQuery, page_size: 5, sort_by: "updated_at", sort_dir: "desc" },
    { enabled: searchActive },
  );
  const taskResults = useMemo(() => (searchActive ? (found?.items ?? []) : []), [searchActive, found]);

  const commands = useMemo<Command[]>(() => {
    const go = (path: string) => () => router.push(path);
    const list: Command[] = [
      { id: "new-task", label: "New task", group: "Actions", keywords: ["create", "add"], run: () => openNewTask() },
      { id: "nav-board", label: "Go to Board", group: "Navigate", keywords: ["home", "kanban", "dashboard"], run: go("/") },
      { id: "nav-tasks", label: "Go to Tasks", group: "Navigate", keywords: ["table", "list"], run: go("/tasks") },
      { id: "nav-week", label: "Go to My week", group: "Navigate", keywords: ["plan", "schedule", "calendar"], run: go("/week") },
      { id: "nav-traces", label: "Go to ORBIT activity", group: "Navigate", keywords: ["history", "what orbit did", "assistant"], run: go("/traces") },
      { id: "nav-profile", label: "Go to Profile", group: "Navigate", keywords: ["settings", "account"], run: go("/profile") },
    ];
    if (isManager) {
      list.push(
        { id: "nav-insights", label: "Go to Insights", group: "Navigate", keywords: ["analytics", "charts"], run: go("/insights") },
        { id: "nav-admin", label: "Go to Admin", group: "Navigate", keywords: ["reminders", "users", "connections", "notifications"], run: go("/admin") },
      );
    }
    for (const prompt of ["Plan my day", "Show my pending tasks", "What are my overdue tasks?"]) {
      list.push({ id: `ask-${prompt}`, label: prompt, group: "Ask ORBIT", hint: "Ask ORBIT", keywords: ["ask", "orbit"], run: () => void ask(prompt) });
    }
    for (const task of taskResults) {
      list.push({ id: `task-${task.id}`, label: task.title, group: "Tasks", hint: task.status.replace("_", " ").toLowerCase(), run: go(`/tasks/${task.id}`) });
    }
    return list;
  }, [router, isManager, ask, openNewTask, taskResults]);

  const results = useMemo(() => {
    const matches = filterCommands(commands, query);
    const trimmed = query.trim();
    // Free text can always be sent to ORBIT.
    if (trimmed.length > 2) {
      matches.push({ id: "ask-free", label: `Ask ORBIT: ${trimmed}`, group: "Ask ORBIT", run: () => void ask(trimmed) });
    }
    return matches;
  }, [commands, query, ask]);

  useEffect(() => setActive(0), [query]);

  if (!open) return null;

  const run = (command: Command | undefined) => {
    if (!command) return;
    onClose();
    command.run();
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((i) => moveIndex(i, 1, results.length));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((i) => moveIndex(i, -1, results.length));
    } else if (e.key === "Enter") {
      e.preventDefault();
      run(results[active]);
    }
  };

  const ICONS: Record<string, React.ReactNode> = {
    "new-task": <Plus className="h-4 w-4" />,
    "nav-board": <LayoutDashboard className="h-4 w-4" />,
    "nav-tasks": <ListChecks className="h-4 w-4" />,
    "nav-insights": <BarChart3 className="h-4 w-4" />,
    "nav-traces": <Activity className="h-4 w-4" />,
    "nav-admin": <Settings2 className="h-4 w-4" />,
    "nav-profile": <UserCircle className="h-4 w-4" />,
  };

  let lastGroup = "";
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/60 px-4 pt-[14vh] animate-fade-in" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div ref={panelRef} role="dialog" aria-modal="true" aria-label="Command palette" className="w-full max-w-xl overflow-hidden rounded-modal border border-line bg-surface-1 shadow-2xl">
        <div className="flex items-center gap-2.5 border-b border-line px-4">
          <Search className="h-4 w-4 text-fg-faint" aria-hidden />
          <input
            data-autofocus
            role="combobox"
            aria-expanded
            aria-controls="palette-list"
            aria-activedescendant={results[active] ? `palette-${results[active].id}` : undefined}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Search tasks, jump to a page, or ask ORBIT"
            className="h-12 flex-1 bg-transparent text-sm text-fg placeholder:text-fg-faint focus:outline-none"
          />
          <Kbd>Esc</Kbd>
        </div>
        <ul id="palette-list" role="listbox" className="max-h-[50vh] overflow-y-auto p-1.5">
          {results.length === 0 && <li className="px-3 py-6 text-center text-xs text-fg-muted">No matches</li>}
          {results.map((command, index) => {
            const showGroup = command.group !== lastGroup;
            lastGroup = command.group;
            return (
              <React.Fragment key={command.id}>
                {showGroup && <li role="presentation" className="section-label px-3 pb-1 pt-2">{command.group}</li>}
                <li
                  id={`palette-${command.id}`}
                  role="option"
                  aria-selected={index === active}
                  onMouseMove={() => setActive(index)}
                  onClick={() => run(command)}
                  className={cn("flex cursor-pointer items-center gap-3 rounded-control px-3 py-2 text-[13px]", index === active ? "bg-surface-3 text-fg" : "text-fg-muted")}
                >
                  <span className="text-fg-faint" aria-hidden>{ICONS[command.id] ?? <Bot className="h-4 w-4" />}</span>
                  <span className="flex-1 truncate">{command.label}</span>
                  {command.hint && <span className="text-[11px] text-fg-faint">{command.hint}</span>}
                  {index === active && <CornerDownLeft className="h-3 w-3 text-fg-faint" aria-hidden />}
                </li>
              </React.Fragment>
            );
          })}
        </ul>
      </div>
    </div>
  );
}
