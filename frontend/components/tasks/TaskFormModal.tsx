"use client";

import React, { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Input, Select, Textarea } from "@/components/ui/Field";
import { Modal } from "@/components/ui/Overlay";
import { useAuth } from "@/lib/auth";
import { ALL_STATUSES, PRIORITIES, PRIORITY_LABEL, STATUS_LABEL } from "@/lib/constants";
import { useCreateTask, useUpdateTask, useUsers } from "@/lib/hooks";
import type { Task, TaskPriority, TaskStatus } from "@/types";

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
            {editing ? "Save changes" : "Create task"}
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
          placeholder="Deploy the frontend to staging"
          error={submitted ? errors.title : null}
          onChange={(e) => set("title", e.target.value)}
        />
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
