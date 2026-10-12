/** Pure helpers for showing how the agents handled a request. */

import type { AgentExecutionTrace, AgentStep } from "@/types";

/** The parts of a run (a chat reply's metadata or a stored trace) the diagram needs. */
export interface RunLike {
  steps?: AgentStep[] | null;
  agents_invoked?: string[];
  node_durations_ms?: Record<string, number>;
  tool_calls_made?: string[];
  intent?: string | null;
  confidence?: number | null;
  classifier?: string | null;
  status?: string | null;
  total_duration_ms?: number | null;
  error_message?: string | null;
}

export const AGENT_NAME: Record<string, string> = {
  supervisor: "Supervisor",
  task_agent: "Task agent",
  planner_agent: "Planner agent",
  recommendation_agent: "Recommendation agent",
  review_agent: "Review agent",
};

export const AGENT_ROLE: Record<string, string> = {
  supervisor: "Reads the request and decides which agent handles it",
  task_agent: "Creates, updates, completes and finds tasks",
  planner_agent: "Builds your day plan from your real tasks",
  recommendation_agent: "Finds overdue work and workload problems",
  review_agent: "Asks for your approval before anything is deleted",
};

export const SPECIALISTS = ["task_agent", "planner_agent", "recommendation_agent", "review_agent"] as const;

const CLASSIFIER_LABEL: Record<string, string> = {
  llm: "Gemini AI",
  rules: "built-in rules",
  flow: "approval answer",
};

export function classifierLabel(classifier: string | null | undefined): string {
  return classifier ? (CLASSIFIER_LABEL[classifier] ?? classifier) : "unknown";
}

/** "get_tasks_due_today" -> "Get tasks due today". */
export function toolLabel(name: string): string {
  const spaced = name.replace(/_/g, " ").trim();
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

export function agentName(node: string): string {
  return AGENT_NAME[node] ?? node;
}

/**
 * The ordered steps of a run. Runs stored before steps were recorded are rebuilt from the agent
 * list, per-agent timings and tool list, so old history still draws a diagram.
 */
export function normalizeSteps(run: RunLike): AgentStep[] {
  if (run.steps && run.steps.length > 0) return run.steps;
  const nodes = run.agents_invoked && run.agents_invoked.length > 0 ? run.agents_invoked : ["supervisor"];
  return nodes.map((node, index) => {
    const step: AgentStep = { node, duration_ms: run.node_durations_ms?.[node] ?? 0 };
    if (node === "supervisor") {
      step.intent = run.intent;
      step.confidence = run.confidence;
      step.classifier = run.classifier;
    } else if (index === nodes.length - 1 && run.tool_calls_made && run.tool_calls_made.length > 0) {
      step.tools = run.tool_calls_made;
    }
    return step;
  });
}

export type Outcome = { tone: "ok" | "warn" | "danger"; label: string };

export function outcomeOf(run: RunLike): Outcome {
  switch (run.status) {
    case "NEEDS_CONFIRMATION":
      return { tone: "warn", label: "Waiting for your approval" };
    case "TIMEOUT":
      return { tone: "danger", label: "Took too long" };
    case "FAILURE":
      return { tone: "danger", label: "Failed" };
    default:
      return { tone: "ok", label: "Replied" };
  }
}

/** The agent that did the work: the last non-supervisor step. */
export function specialistOf(run: RunLike): string | null {
  const steps = normalizeSteps(run).filter((s) => s.node !== "supervisor");
  return steps.length > 0 ? steps[steps.length - 1].node : null;
}

export interface RunSummary {
  total: number;
  failures: number;
  byAgent: Record<string, { runs: number; avgMs: number }>;
  classifier: Record<string, number>;
  lastAgent: string | null;
}

/** Counts per agent, average time per agent, and how intents were classified. */
export function summarizeRuns(runs: AgentExecutionTrace[]): RunSummary {
  const byAgent: RunSummary["byAgent"] = {};
  const classifier: Record<string, number> = {};
  const totals: Record<string, number> = {};
  let failures = 0;
  for (const run of runs) {
    const key = run.classifier ?? "unknown";
    classifier[key] = (classifier[key] ?? 0) + 1;
    if (run.status === "FAILURE" || run.status === "TIMEOUT") failures += 1;
    const agent = specialistOf(run);
    if (!agent) continue;
    const entry = (byAgent[agent] ??= { runs: 0, avgMs: 0 });
    entry.runs += 1;
    totals[agent] = (totals[agent] ?? 0) + (run.node_durations_ms?.[agent] ?? run.total_duration_ms ?? 0);
  }
  for (const [agent, entry] of Object.entries(byAgent)) entry.avgMs = totals[agent] / entry.runs;
  return { total: runs.length, failures, byAgent, classifier, lastAgent: runs.length > 0 ? specialistOf(runs[0]) : null };
}
