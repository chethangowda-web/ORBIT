"use client";

import React, { useState } from "react";
import Link from "next/link";
import {
  DndContext,
  DragOverlay,
  KeyboardSensor,
  PointerSensor,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import { ChevronRight, GripVertical, Plus } from "lucide-react";
import { Avatar } from "@/components/ui/Primitives";
import { PriorityBadge } from "@/components/ui/Badge";
import { cn } from "@/lib/cn";
import { BOARD_STATUSES, NEXT_STATUS, STATUS_LABEL } from "@/lib/constants";
import { DueChip, TagList } from "./TaskParts";
import type { Task, TaskStatus } from "@/types";

const LANE_DOT: Record<TaskStatus, string> = {
  TODO: "bg-fg-muted",
  IN_PROGRESS: "bg-info",
  REVIEW: "bg-warn",
  DONE: "bg-ok",
  CANCELLED: "bg-fg-faint",
};

function CardBody({ task, onAdvance, dragging }: { task: Task; onAdvance?: (task: Task) => void; dragging?: boolean }) {
  const next = NEXT_STATUS[task.status];
  return (
    <div
      className={cn(
        "rounded-panel border border-line bg-surface-2 p-3 transition-colors",
        dragging ? "border-accent shadow-xl" : "hover:border-fg-faint",
      )}
    >
      <div className="mb-2 flex items-center justify-between gap-2">
        <PriorityBadge priority={task.priority} />
        <DueChip task={task} />
      </div>
      <Link
        href={`/tasks/${task.id}`}
        className="mb-1.5 line-clamp-2 block text-[13px] font-medium leading-snug text-fg hover:text-accent"
      >
        {task.title}
      </Link>
      {task.description && <p className="mb-2 line-clamp-2 text-xs text-fg-muted">{task.description}</p>}
      <TagList tags={task.tags} />
      <div className="mt-2.5 flex items-center justify-between border-t border-line-subtle pt-2">
        <span className="flex min-w-0 items-center gap-1.5 text-xs text-fg-muted">
          <Avatar name={task.assignee?.display_name} size="sm" />
          <span className="truncate">{task.assignee?.display_name ?? "Unassigned"}</span>
        </span>
        {next && onAdvance && (
          <button
            type="button"
            onClick={() => onAdvance(task)}
            aria-label={`Move "${task.title}" to ${STATUS_LABEL[next]}`}
            className="inline-flex h-6 items-center gap-0.5 rounded-control px-1.5 text-[11px] text-fg-muted transition-colors hover:bg-surface-3 hover:text-fg"
          >
            {STATUS_LABEL[next]}
            <ChevronRight className="h-3 w-3" aria-hidden />
          </button>
        )}
      </div>
    </div>
  );
}

function DraggableCard({ task, onAdvance }: { task: Task; onAdvance: (task: Task) => void }) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({ id: task.id, data: { task } });
  return (
    <div ref={setNodeRef} className={cn("group relative", isDragging && "opacity-30")}>
      <button
        type="button"
        aria-label={`Drag "${task.title}". Press space to pick up, arrow keys to move, space to drop.`}
        className="absolute left-0 top-1/2 z-10 -ml-0.5 flex h-8 w-4 -translate-y-1/2 cursor-grab items-center justify-center text-fg-faint opacity-0 hover:text-fg focus-visible:opacity-100 group-hover:opacity-100"
        {...listeners}
        {...attributes}
      >
        <GripVertical className="h-3.5 w-3.5" aria-hidden />
      </button>
      <CardBody task={task} onAdvance={onAdvance} />
    </div>
  );
}

function Lane({
  status,
  tasks,
  total,
  onAdd,
  onAdvance,
}: {
  status: TaskStatus;
  tasks: Task[];
  total?: number;
  onAdd: (status: TaskStatus) => void;
  onAdvance: (task: Task) => void;
}) {
  const { setNodeRef, isOver } = useDroppable({ id: status });
  const hidden = total !== undefined && total > tasks.length ? total - tasks.length : 0;
  return (
    <section
      ref={setNodeRef}
      aria-label={`${STATUS_LABEL[status]} lane, ${tasks.length} tasks`}
      className={cn(
        "flex min-h-[200px] min-w-[220px] flex-1 basis-0 flex-col rounded-panel border bg-surface-1 transition-colors",
        isOver ? "border-accent bg-accent/5" : "border-line",
      )}
    >
      <header className="flex items-center justify-between border-b border-line-subtle px-3 py-2.5">
        <div className="flex items-center gap-2">
          <span className={cn("h-2 w-2 rounded-full", LANE_DOT[status])} aria-hidden />
          <h2 className={cn("text-xs font-semibold", status === "DONE" ? "text-ok" : "text-fg")}>{STATUS_LABEL[status]}</h2>
          <span className="num rounded-control bg-surface-3 px-1.5 text-[11px] text-fg-muted">{total ?? tasks.length}</span>
        </div>
        <button
          type="button"
          onClick={() => onAdd(status)}
          aria-label={`Add task to ${STATUS_LABEL[status]}`}
          className="rounded-control p-1 text-fg-faint transition-colors hover:bg-surface-2 hover:text-fg"
        >
          <Plus className="h-3.5 w-3.5" />
        </button>
      </header>
      <div className="flex-1 space-y-2 overflow-y-auto p-2.5">
        {tasks.length === 0 ? (
          <p className="py-8 text-center text-xs text-fg-faint">Nothing here</p>
        ) : (
          tasks.map((task) => <DraggableCard key={task.id} task={task} onAdvance={onAdvance} />)
        )}
        {hidden > 0 && (
          <Link href={`/tasks?status=${status}`} className="block py-1 text-center text-[11px] text-accent hover:underline">
            {hidden} more in Tasks
          </Link>
        )}
      </div>
    </section>
  );
}

interface BoardProps {
  tasks: Task[];
  /** Total task count per lane when the lane shows only a subset (e.g. recent done). */
  totals?: Partial<Record<TaskStatus, number>>;
  onMove: (task: Task, status: TaskStatus) => void;
  onAdd: (status: TaskStatus) => void;
}

export function KanbanBoard({ tasks, totals, onMove, onAdd }: BoardProps) {
  const [active, setActive] = useState<Task | null>(null);
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor),
  );

  const handleStart = (event: DragStartEvent) => setActive((event.active.data.current?.task as Task) ?? null);
  const handleEnd = (event: DragEndEvent) => {
    setActive(null);
    const task = event.active.data.current?.task as Task | undefined;
    const target = event.over?.id as TaskStatus | undefined;
    if (task && target && BOARD_STATUSES.includes(target) && target !== task.status) onMove(task, target);
  };

  return (
    <DndContext sensors={sensors} onDragStart={handleStart} onDragEnd={handleEnd} onDragCancel={() => setActive(null)}>
      <div className="flex min-h-0 flex-1 gap-3 overflow-x-auto pb-2">
        {BOARD_STATUSES.map((status) => (
          <Lane
            key={status}
            status={status}
            tasks={tasks.filter((t) => t.status === status)}
            total={totals?.[status]}
            onAdd={onAdd}
            onAdvance={(task) => {
              const next = NEXT_STATUS[task.status];
              if (next) onMove(task, next);
            }}
          />
        ))}
      </div>
      <DragOverlay>{active ? <CardBody task={active} dragging /> : null}</DragOverlay>
    </DndContext>
  );
}

