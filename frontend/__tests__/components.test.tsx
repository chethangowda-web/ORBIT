import React, { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { WorkflowDiagram } from "@/components/agent/WorkflowDiagram";
import { PriorityBadge, RunStatusBadge, StatusBadge } from "@/components/ui/Badge";
import { Button, IconButton } from "@/components/ui/Button";
import { Input } from "@/components/ui/Field";
import { ConfirmDialog, Modal } from "@/components/ui/Overlay";
import { Pagination } from "@/components/ui/Pagination";
import { parseTags, validateTask } from "@/components/tasks/TaskFormModal";

describe("badges", () => {
  it("show readable labels, not raw enum values", () => {
    render(
      <>
        <StatusBadge status="IN_PROGRESS" />
        <StatusBadge status="TODO" />
        <PriorityBadge priority="CRITICAL" />
      </>,
    );
    expect(screen.getByText("In progress")).toBeInTheDocument();
    expect(screen.getByText("To do")).toBeInTheDocument();
    expect(screen.getByText("Critical")).toBeInTheDocument();
  });

  it("fall back safely for unknown values", () => {
    render(<StatusBadge status="WEIRD" />);
    expect(screen.getByText("WEIRD")).toBeInTheDocument();
  });

  it("describe agent run outcomes", () => {
    render(<RunStatusBadge status="NEEDS_CONFIRMATION" />);
    expect(screen.getByText("Needs your approval")).toBeInTheDocument();
  });
});

describe("buttons and fields", () => {
  it("icon buttons always expose an accessible name", () => {
    render(<IconButton label="Delete task" />);
    expect(screen.getByRole("button", { name: "Delete task" })).toBeInTheDocument();
  });

  it("loading buttons are disabled and busy", () => {
    render(<Button loading>Save</Button>);
    const button = screen.getByRole("button", { name: /save/i });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("aria-busy", "true");
  });

  it("inputs are labelled and announce errors", () => {
    render(<Input label="Title" error="A title is required." />);
    const input = screen.getByLabelText("Title");
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input).toHaveAccessibleDescription("A title is required.");
  });
});

describe("Modal", () => {
  function Harness({ onClose = () => {} }: { onClose?: () => void }) {
    const [open, setOpen] = useState(false);
    return (
      <>
        <button onClick={() => setOpen(true)}>Open</button>
        <Modal open={open} onClose={() => { setOpen(false); onClose(); }} title="Edit task">
          <input aria-label="Name" />
          <button>Inside</button>
        </Modal>
      </>
    );
  }

  it("is exposed as a labelled modal dialog", async () => {
    render(<Harness />);
    await userEvent.click(screen.getByText("Open"));
    expect(screen.getByRole("dialog", { name: "Edit task" })).toHaveAttribute("aria-modal", "true");
  });

  it("closes on Escape and returns focus to the trigger", async () => {
    const onClose = vi.fn();
    render(<Harness onClose={onClose} />);
    const trigger = screen.getByText("Open");
    await userEvent.click(trigger);
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(onClose).toHaveBeenCalled();
    expect(trigger).toHaveFocus();
  });

  it("keeps Tab focus inside the dialog", async () => {
    render(<Harness />);
    await userEvent.click(screen.getByText("Open"));
    const dialog = screen.getByRole("dialog");
    for (let i = 0; i < 6; i++) {
      await userEvent.tab();
      expect(dialog.contains(document.activeElement)).toBe(true);
    }
  });

  it("locks page scroll while open and restores it after", async () => {
    render(<Harness />);
    await userEvent.click(screen.getByText("Open"));
    expect(document.body.style.overflow).toBe("hidden");
    await userEvent.keyboard("{Escape}");
    expect(document.body.style.overflow).not.toBe("hidden");
  });
});

describe("ConfirmDialog", () => {
  it("only fires onConfirm from the confirm button", async () => {
    const onConfirm = vi.fn();
    const onClose = vi.fn();
    render(<ConfirmDialog open title="Delete?" description="Gone." confirmLabel="Delete task" onConfirm={onConfirm} onClose={onClose} />);
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onConfirm).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Delete task" }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it("focuses the confirm button first so Enter is deliberate, not accidental", () => {
    render(<ConfirmDialog open title="Delete?" description="Gone." confirmLabel="Delete task" onConfirm={() => {}} onClose={() => {}} />);
    expect(screen.getByRole("button", { name: "Delete task" })).toHaveFocus();
  });

  it("disables the confirm button while working", () => {
    render(<ConfirmDialog open loading title="t" description="d" onConfirm={() => {}} onClose={() => {}} />);
    expect(screen.getByRole("button", { name: "Working..." })).toBeDisabled();
  });
});

describe("Pagination", () => {
  const meta = { page: 2, page_size: 10, total: 25, total_pages: 3 };

  it("reports the visible range and total", () => {
    render(<Pagination meta={meta} noun="tasks" onPageChange={() => {}} />);
    expect(screen.getByText("11-20")).toBeInTheDocument();
    expect(screen.getByText("25")).toBeInTheDocument();
  });

  it("navigates and disables at the edges", async () => {
    const onPageChange = vi.fn();
    const { rerender } = render(<Pagination meta={meta} onPageChange={onPageChange} />);
    await userEvent.click(screen.getByRole("button", { name: /next/i }));
    expect(onPageChange).toHaveBeenCalledWith(3);
    rerender(<Pagination meta={{ ...meta, page: 1 }} onPageChange={onPageChange} />);
    expect(screen.getByRole("button", { name: /previous/i })).toBeDisabled();
  });

  it("renders nothing for an empty result set", () => {
    const { container } = render(<Pagination meta={{ page: 1, page_size: 10, total: 0, total_pages: 0 }} onPageChange={() => {}} />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("WorkflowDiagram", () => {
  const planRun = {
    steps: [
      { node: "supervisor", duration_ms: 2100, intent: "PLAN_DAY", confidence: 0.92, classifier: "llm" },
      { node: "planner_agent", duration_ms: 6400, tools: ["get_overdue_tasks", "get_user_tasks"] },
    ],
    status: "SUCCESS",
    total_duration_ms: 8500,
  };

  it("tells the story in everyday words, with no technical terms", () => {
    const { container } = render(<WorkflowDiagram run={planRun} request="plan my day" />);
    expect(screen.getByText(/plan my day/)).toBeInTheDocument();
    expect(screen.getByText("Coordinator")).toBeInTheDocument();
    expect(screen.getByText("Planning your day")).toBeInTheDocument();
    expect(screen.getByText(/Understood by AI/)).toBeInTheDocument();
    expect(screen.getByText("Day planner")).toBeInTheDocument();
    const steps = within(screen.getByRole("list", { name: "What it did, in order" })).getAllByRole("listitem");
    expect(steps.map((li) => li.textContent)).toEqual([expect.stringContaining("Checked what is late"), expect.stringContaining("Checked your tasks")]);
    expect(screen.getByText("Done")).toBeInTheDocument();
    expect(screen.getByText(/Took 8.5s/)).toBeInTheDocument();
    for (const jargon of [/supervisor/i, /intent/i, /\btools?\b/i, /get_overdue_tasks/, /PLAN_DAY/, /gemini/i, /\bllm\b/i, /confidence/i, /\d+%/]) {
      expect(container.textContent).not.toMatch(jargon);
    }
  });

  it("says when approval is needed or the request did not work, without exposing the error", () => {
    const { rerender, container } = render(<WorkflowDiagram run={{ ...planRun, status: "NEEDS_CONFIRMATION" }} />);
    expect(screen.getByText("Waiting for your approval")).toBeInTheDocument();
    rerender(<WorkflowDiagram run={{ ...planRun, status: "FAILURE", error_message: "sqlalchemy.exc.OperationalError" }} />);
    expect(screen.getByText("Didn't work")).toBeInTheDocument();
    expect(container.textContent).not.toMatch(/sqlalchemy/i);
    expect(screen.getByText(/Something went wrong on our side/)).toBeInTheDocument();
  });

  it("lists, in plain words, what the multi-step helper changed", () => {
    render(
      <WorkflowDiagram
        run={{
          steps: [
            { node: "supervisor", duration_ms: 1500, intent: "MULTI_STEP", classifier: "llm" },
            {
              node: "tool_agent",
              duration_ms: 9000,
              tools: ["search_tasks", "find_person", "update_task"],
              actions: ["Changed *Renew the licence*: priority is now high, now with Rahul"],
            },
          ],
          status: "SUCCESS",
        }}
      />,
    );
    expect(screen.getByText("Multi-step helper")).toBeInTheDocument();
    expect(screen.getByText("Working through several steps")).toBeInTheDocument();
    const changes = within(screen.getByRole("list", { name: "Changes made" })).getAllByRole("listitem");
    expect(changes).toHaveLength(1);
    expect(changes[0]).toHaveTextContent("Changed Renew the licence: priority is now high, now with Rahul");
    expect(changes[0].textContent).not.toContain("*");
    const steps = within(screen.getByRole("list", { name: "What it did, in order" })).getAllByRole("listitem");
    expect(steps.map((li) => li.textContent)).toEqual([
      expect.stringContaining("Looked for matching tasks"),
      expect.stringContaining("Looked up a teammate"),
      expect.stringContaining("Changed the task"),
    ]);
  });

  it("still draws a request that was saved before steps were recorded", () => {
    render(<WorkflowDiagram run={{ agents_invoked: ["supervisor", "task_agent"], tool_calls_made: ["create_task"], intent: "CREATE_TASK", status: "SUCCESS" }} />);
    expect(screen.getByText("Task helper")).toBeInTheDocument();
    const steps = within(screen.getByRole("list", { name: "What it did, in order" })).getAllByRole("listitem");
    expect(steps).toHaveLength(1);
    expect(steps[0]).toHaveTextContent("Added the task");
  });
});

describe("task form helpers", () => {
  it("normalises tags: trims, strips #, dedupes, caps length and count", () => {
    expect(parseTags(" api, #api ,frontend,,  release ")).toEqual(["api", "frontend", "release"]);
    expect(parseTags("a".repeat(60))[0]).toHaveLength(40);
    expect(parseTags(Array.from({ length: 15 }, (_, i) => `t${i}`).join(","))).toHaveLength(10);
    expect(parseTags("")).toEqual([]);
  });

  it("requires a non-blank title within the length limit", () => {
    expect(validateTask({ title: "   ", description: "" }).title).toMatch(/required/i);
    expect(validateTask({ title: "x".repeat(256), description: "" }).title).toMatch(/255/);
    expect(validateTask({ title: "Ship it", description: "" })).toEqual({});
  });

  it("limits description length", () => {
    expect(validateTask({ title: "ok", description: "x".repeat(5001) }).description).toMatch(/5,000/);
  });
});
