/** Pure helpers for showing how ORBIT's helpers handled a request, in everyday words. */

import type { AgentExecutionTrace, AgentStep } from "@/types";

/** The parts of a run (a chat reply's metadata or a stored record) the diagram needs. */
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

/** The members of the ORBIT team, by their internal id. */
export const AGENT_NAME: Record<string, string> = {
  supervisor: "Coordinator",
  task_agent: "Task helper",
  planner_agent: "Day planner",
  recommendation_agent: "Advisor",
  review_agent: "Reviewer",
  tool_agent: "Multi-step helper",
};

export const AGENT_ROLE: Record<string, string> = {
  supervisor: "Reads your request and decides who helps",
  task_agent: "Adds, changes, finishes and finds tasks",
  planner_agent: "Plans your day from your real tasks",
  recommendation_agent: "Spots late work and busy teammates",
  review_agent: "Checks with you before anything is deleted",
  tool_agent: "Works through bigger requests step by step",
};

export const SPECIALISTS = ["task_agent", "planner_agent", "recommendation_agent", "review_agent", "tool_agent"] as const;

const INTENT_LABEL: Record<string, string> = {
  CREATE_TASK: "Adding a task",
  UPDATE_TASK: "Changing a task",
  DELETE_TASK: "Deleting a task",
  COMPLETE_TASK: "Finishing a task",
  GET_MY_TASKS: "Showing your tasks",
  GET_OVERDUE_TASKS: "Checking late work",
  SEARCH_TASKS: "Finding a task",
  GET_TASK_DETAIL: "Showing a task",
  PLAN_DAY: "Planning your day",
  GET_RECOMMENDATIONS: "Team advice",
  HELP: "Help",
  GREETING: "Saying hello",
  MULTI_STEP: "Working through several steps",
  UNKNOWN: "Not sure what you meant",
};

export function intentLabel(intent: string | null | undefined): string {
  if (!intent) return INTENT_LABEL.UNKNOWN;
  return INTENT_LABEL[intent] ?? sentence(intent.replace(/_/g, " ").toLowerCase());
}

const CLASSIFIER_LABEL: Record<string, string> = {
  llm: "AI",
  quick: "a quick check",
  rules: "a quick check (the AI was busy)",
  flow: "your answer",
};

/** How the request was understood, as a short phrase that completes "Understood by ...". */
export function classifierLabel(classifier: string | null | undefined): string {
  return classifier ? (CLASSIFIER_LABEL[classifier] ?? classifier) : "ORBIT";
}

/** What each internal action looks like to a person: a short past-tense sentence. */
const STEP_LABEL: Record<string, string> = {
  create_task: "Added the task",
  update_task: "Changed the task",
  complete_task: "Marked the task as done",
  delete_task: "Deleted the task",
  get_task_by_id: "Opened the task",
  search_tasks: "Looked for matching tasks",
  get_user_tasks: "Checked your tasks",
  get_overdue_tasks: "Checked what is late",
  get_tasks_due_today: "Checked what is due today",
  get_task_stats: "Counted tasks by status",
  get_team_workload: "Checked who is busy",
  get_user_by_name: "Looked up a teammate",
  get_all_users: "Looked up the team",
  get_task: "Opened the task",
  find_person: "Looked up a teammate",
  list_team: "Looked up the team",
  team_workload: "Checked who is busy",
  task_stats: "Counted tasks by status",
};

function sentence(text: string): string {
  const spaced = text.replace(/_/g, " ").trim();
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

/** "get_overdue_tasks" -> "Checked what is late". Unknown actions fall back to readable words. */
export function stepLabel(name: string): string {
  return STEP_LABEL[name] ?? sentence(name);
}

export function agentName(node: string): string {
  return AGENT_NAME[node] ?? sentence(node);
}

/**
 * The ordered steps of a run. Runs saved before steps were recorded are rebuilt from the helper
 * list, per-helper timings and action list, so old history still draws a diagram.
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
      return { tone: "danger", label: "Didn't work" };
    default:
      return { tone: "ok", label: "Done" };
  }
}

/** The team member that did the work: the last step that is not the Coordinator. */
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

/** Counts per helper, average time per helper, and how requests were understood. */
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
