"use client";

import React, { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Copy, UserSearch } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Input, Select, Textarea } from "@/components/ui/Field";
import { Modal } from "@/components/ui/Overlay";
import { api } from "@/lib/api-client";
import { useAuth } from "@/lib/auth";
import { ALL_STATUSES, PRIORITIES, PRIORITY_LABEL, STATUS_LABEL } from "@/lib/constants";
import { useCreateTask, useUpdateTask, useUsers } from "@/lib/hooks";
import type { AssigneeSuggestion, Task, TaskPriority, TaskStatus } from "@/types";

interface Props {
  open: boolean;
  onClose: () => void;
  /** When set the form edits this task; otherwise it creates a new one. */
  task?: Task | null;
  defaultStatus?: TaskStatus;
}

interface FormState {
  title: string;
  description: string;
  status: TaskStatus;
  priority: TaskPriority;
  assigneeId: string;
  dueDate: string;
  tags: string;
}

const EMPTY: FormState = {
  title: "",
  description: "",
  status: "TODO",
  priority: "MEDIUM",
  assigneeId: "",
  dueDate: "",
  tags: "",
};

export function parseTags(raw: string): string[] {
  const seen = new Set<string>();
  for (const part of raw.split(",")) {
    const tag = part.trim().replace(/^#/, "");
    if (tag) seen.add(tag.slice(0, 40));
  }
  return Array.from(seen).slice(0, 10);
}

export function validateTask(form: Pick<FormState, "title" | "description">): Partial<Record<"title" | "description", string>> {
  const errors: Partial<Record<"title" | "description", string>> = {};
  const title = form.title.trim();
  if (!title) errors.title = "A title is required.";
  else if (title.length > 255) errors.title = "Keep the title under 255 characters.";
  if (form.description.length > 5000) errors.description = "Keep the description under 5,000 characters.";
  return errors;
}

function fromTask(task: Task): FormState {
  return {
    title: task.title,
    description: task.description ?? "",
    status: task.status,
    priority: task.priority,
    assigneeId: task.assignee_id ?? "",
    dueDate: task.due_date ?? "",
    tags: (task.tags ?? []).join(", "),
  };
}

export function TaskFormModal({ open, onClose, task, defaultStatus = "TODO" }: Props) {
  const { user, isManager } = useAuth();
  const { data: users = [] } = useUsers();
  const [form, setForm] = useState<FormState>(EMPTY);
  const [submitted, setSubmitted] = useState(false);

  const editing = Boolean(task);
  const create = useCreateTask(() => onClose());
  const update = useUpdateTask(() => onClose());
  const pending = create.isPending || update.isPending;

  // Reset the form each time the dialog opens.
  useEffect(() => {
    if (!open) return;
    setSubmitted(false);
    setForm(task ? fromTask(task) : { ...EMPTY, status: defaultStatus, assigneeId: isManager ? "" : (user?.id ?? "") });
  }, [open, task, defaultStatus, isManager, user?.id]);

  // Ask before creating a double: look for the same or a very similar open task as the title is typed.
  const [typedTitle, setTypedTitle] = useState("");
  useEffect(() => {
    const timer = setTimeout(() => setTypedTitle(form.title.trim()), 400);
    return () => clearTimeout(timer);
  }, [form.title]);
  const similarQuery = useQuery({
    queryKey: ["similar-tasks", typedTitle],
    queryFn: () => api.tasks.similar(typedTitle),
    enabled: open && !editing && typedTitle.length >= 3,
    staleTime: 15_000,
  });
  const similar = !editing && typedTitle.length >= 3 ? (similarQuery.data ?? []) : [];
  const hasSame = similar.some((s) => s.same);

  // Managers can ask who has room before choosing an assignee.
  const [suggestions, setSuggestions] = useState<AssigneeSuggestion[] | null>(null);
  const [suggesting, setSuggesting] = useState(false);
  useEffect(() => {
    if (!open) setSuggestions(null);
  }, [open]);
  const suggest = async () => {
    setSuggesting(true);
    try {
      setSuggestions(await api.planning.suggestAssignee());
    } catch {
      setSuggestions([]);
    } finally {
      setSuggesting(false);
    }
  };

  const set = <K extends keyof FormState>(key: K, value: FormState[K]) => setForm((f) => ({ ...f, [key]: value }));
  const errors = validateTask(form);
  // Employees can only pick themselves, plus whoever the task is already assigned to, so the form
  // shows the real assignee and an edit that leaves it alone is not rejected.
  const assignable = isManager ? users : users.filter((u) => u.id === user?.id || u.id === task?.assignee_id);

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    setSubmitted(true);
    if (Object.keys(errors).length > 0) return;

    const body = {
      title: form.title.trim(),
      description: form.description.trim() || undefined,
      priority: form.priority,
      assignee_id: form.assigneeId || null,
      due_date: form.dueDate || null,
      tags: parseTags(form.tags),
    };
    if (task) {
      update.mutate({ id: task.id, body: { ...body, description: form.description.trim() || null, status: form.status } });
    } else {
      create.mutate(body);
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={editing ? "Edit task" : "New task"}
      description={editing ? undefined : "Assigned work shows up on the board and in Google Chat."}
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={pending}>
            Cancel
          </Button>
          <Button variant="primary" type="submit" form="task-form" loading={pending}>
            {editing ? "Save changes" : hasSame ? "Create anyway" : "Create task"}
          </Button>
        </>
      }
    >
      <form id="task-form" onSubmit={submit} noValidate className="space-y-3.5">
        <Input
          label="Title"
          required
          data-autofocus
          value={form.title}
          maxLength={255}
          placeholder="Prepare the Friday client presentation"
          error={submitted ? errors.title : null}
          onChange={(e) => set("title", e.target.value)}
        />
        {similar.length > 0 && (
          <div role="status" aria-label="Similar tasks" className="rounded-control border border-warn/40 bg-warn/5 p-2.5 text-xs">
            <p className="flex items-center gap-1.5 font-medium text-fg">
              <Copy className="h-3.5 w-3.5 text-warn" aria-hidden />
              {hasSame ? "This task already exists" : "A similar task already exists"}
            </p>
            <ul className="mt-1.5 space-y-1">
              {similar.map((s) => (
                <li key={s.id} className="text-fg-muted">
                  <span className="text-fg">{s.title}</span> ({STATUS_LABEL[s.status as TaskStatus] ?? s.status}
                  {s.assignee ? `, with ${s.assignee}` : ", not assigned"})
                </li>
              ))}
            </ul>
            <p className="mt-1.5 text-fg-faint">{hasSame ? "Create it only if you really want a second copy." : "Check it is not the same piece of work."}</p>
          </div>
        )}
        <Textarea
          label="Description"
          rows={3}
          value={form.description}
          placeholder="Context, acceptance criteria, links"
          error={submitted ? errors.description : null}
          onChange={(e) => set("description", e.target.value)}
        />
        <div className="grid grid-cols-2 gap-3">
          <Select
            label="Priority"
            value={form.priority}
            onChange={(e) => set("priority", e.target.value as TaskPriority)}
            options={PRIORITIES.slice().reverse().map((p) => ({ value: p, label: PRIORITY_LABEL[p] }))}
          />
          {editing ? (
            <Select
              label="Status"
              value={form.status}
              onChange={(e) => set("status", e.target.value as TaskStatus)}
              options={ALL_STATUSES.map((s) => ({ value: s, label: STATUS_LABEL[s] }))}
            />
          ) : (
            <Input label="Due date" type="date" value={form.dueDate} onChange={(e) => set("dueDate", e.target.value)} />
          )}
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Select
            label="Assignee"
            value={form.assigneeId}
            hint={isManager ? undefined : "Employees can only assign to themselves."}
            onChange={(e) => set("assigneeId", e.target.value)}
            options={[
              { value: "", label: "Unassigned" },
              ...assignable.map((u) => ({ value: u.id, label: u.id === user?.id ? `${u.display_name} (you)` : u.display_name })),
            ]}
          />
          {editing && (
            <Input label="Due date" type="date" value={form.dueDate} onChange={(e) => set("dueDate", e.target.value)} />
          )}
        </div>
        {isManager && (
          <div className="-mt-1">
            <Button type="button" size="sm" onClick={() => void suggest()} loading={suggesting}>
              <UserSearch className="h-3.5 w-3.5" aria-hidden /> Who has room?
            </Button>
            {suggestions !== null && (
              <div role="group" aria-label="People with room" className="mt-2 flex flex-wrap gap-1.5">
                {suggestions.length === 0 && <p className="text-xs text-fg-muted">No suggestions right now.</p>}
                {suggestions.map((s) => (
                  <button
                    key={s.user_id}
                    type="button"
                    aria-label={`Assign to ${s.display_name}`}
                    onClick={() => set("assigneeId", s.user_id)}
                    className="rounded-control border border-line bg-surface-2 px-2 py-1 text-left text-xs transition-colors hover:border-accent/60"
                  >
                    <span className="font-medium text-fg">{s.display_name}</span>
                    <span className="ml-1.5 text-fg-muted">{s.reason}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
        <Input
          label="Tags"
          hint="Comma separated, up to 10."
          value={form.tags}
          placeholder="frontend, release"
          onChange={(e) => set("tags", e.target.value)}
        />
      </form>
    </Modal>
  );
}
