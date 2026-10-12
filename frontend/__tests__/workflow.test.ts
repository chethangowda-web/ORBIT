import { describe, expect, it } from "vitest";
import { classifierLabel, normalizeSteps, outcomeOf, specialistOf, summarizeRuns, toolLabel } from "@/lib/workflow";
import type { AgentExecutionTrace } from "@/types";

const run = (over: Partial<AgentExecutionTrace> = {}): AgentExecutionTrace => ({
  id: "1",
  request_id: "r",
  user_id: "u",
  thread_id: "t",
  intent: "PLAN_DAY",
  confidence: 0.9,
  active_agent: "planner_agent",
  agents_invoked: ["supervisor", "planner_agent"],
  tool_calls_made: ["get_overdue_tasks", "get_user_tasks"],
  node_durations_ms: { supervisor: 2000, planner_agent: 6000 },
  total_duration_ms: 8100,
  status: "SUCCESS",
  started_at: "2026-10-12T10:00:00Z",
  completed_at: "2026-10-12T10:00:08Z",
  created_at: "2026-10-12T10:00:08Z",
  ...over,
});

describe("toolLabel", () => {
  it("turns tool ids into readable names", () => {
    expect(toolLabel("get_tasks_due_today")).toBe("Get tasks due today");
    expect(toolLabel("create_task")).toBe("Create task");
  });
});

describe("classifierLabel", () => {
  it("names how the intent was decided", () => {
    expect(classifierLabel("llm")).toBe("Gemini AI");
    expect(classifierLabel("rules")).toBe("built-in rules");
    expect(classifierLabel("flow")).toBe("approval answer");
    expect(classifierLabel(null)).toBe("unknown");
  });
});

describe("normalizeSteps", () => {
  it("uses recorded steps when present", () => {
    const steps = [{ node: "supervisor", duration_ms: 5 }, { node: "task_agent", duration_ms: 9, tools: ["create_task"] }];
    expect(normalizeSteps({ steps })).toBe(steps);
  });

  it("rebuilds old runs from the agent list, timings and tools", () => {
    const steps = normalizeSteps(run({ classifier: "rules" }));
    expect(steps.map((s) => s.node)).toEqual(["supervisor", "planner_agent"]);
    expect(steps[0]).toMatchObject({ intent: "PLAN_DAY", classifier: "rules", duration_ms: 2000 });
    expect(steps[1].tools).toEqual(["get_overdue_tasks", "get_user_tasks"]);
  });

  it("still draws something for a run with no data at all", () => {
    expect(normalizeSteps({}).map((s) => s.node)).toEqual(["supervisor"]);
  });
});

describe("outcomeOf and specialistOf", () => {
  it("maps statuses to a tone and a sentence", () => {
    expect(outcomeOf({ status: "SUCCESS" }).tone).toBe("ok");
    expect(outcomeOf({ status: "NEEDS_CONFIRMATION" }).label).toMatch(/approval/);
    expect(outcomeOf({ status: "TIMEOUT" }).tone).toBe("danger");
    expect(outcomeOf({ status: "FAILURE" }).label).toBe("Failed");
  });

  it("finds the agent that did the work", () => {
    expect(specialistOf(run())).toBe("planner_agent");
    expect(specialistOf({ agents_invoked: ["supervisor"] })).toBeNull();
  });
});

describe("summarizeRuns", () => {
  it("counts runs per agent, averages their time, and tallies classification", () => {
    const summary = summarizeRuns([
      run({ classifier: "llm" }),
      run({ classifier: "rules", node_durations_ms: { supervisor: 1, planner_agent: 2000 } }),
      run({ agents_invoked: ["supervisor", "task_agent"], active_agent: "task_agent", node_durations_ms: { supervisor: 1, task_agent: 100 }, status: "FAILURE" }),
    ]);
    expect(summary.total).toBe(3);
    expect(summary.failures).toBe(1);
    expect(summary.byAgent.planner_agent).toEqual({ runs: 2, avgMs: 4000 });
    expect(summary.byAgent.task_agent.runs).toBe(1);
    expect(summary.classifier).toEqual({ llm: 1, rules: 1, unknown: 1 });
    expect(summary.lastAgent).toBe("planner_agent");
  });
});
