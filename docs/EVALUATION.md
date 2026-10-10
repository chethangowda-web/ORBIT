# EVALUATION.md — AI/Agent Evaluation Strategy
# ORBIT: Multi-Agent AI Task Management System

**Version:** 1.1.0  
**Last Updated:** 2026-10-10

> **Measured results (offline classifier, `pytest tests/eval -s`).** Regression set (`entity_dataset.json`, 40 phrasings with entity checks): 100% intent, 100% entities. Holdout set (`entity_holdout.json`, 26 phrasings written afterwards): the rules first scored **31%** on it, which exposed how brittle keyword rules are on unseen wording; after broadening them it scores 100%, but because those phrasings were then used to tune the rules, treat the holdout as a regression set too and expect lower accuracy on genuinely new wording. This is why an LLM key is recommended in production: the classifier is the safety net, not the primary path.
>
> **Safety property (enforced by `test_questions_are_never_classified_as_changes`).** A question or show/list request never creates, edits, completes or deletes anything. This test caught real bugs: "how many tasks are done?" used to complete a task and "who created the deployment task?" used to create one.
>
> **Status.** Implemented: `tests/eval/intent_dataset.json` (intent accuracy, offline classifier) and `tests/eval/test_agent_evaluation.py` (all core intents end to end, grounding and fallback). The entity, response-quality and tool-call datasets and the LangSmith evaluator described below are planned, not built. The backend suite runs fully offline; set `ORBIT_LIVE_LLM=1` to evaluate against a real model manually.

---

## 1. Overview

ORBIT evaluates agent quality across three dimensions:
1. **Intent Classification Accuracy** — Does the Supervisor correctly identify what the user wants?
2. **Entity Extraction Quality** — Are task fields (title, assignee, priority, due date) extracted correctly?
3. **Response Quality** — Are agent responses helpful, concise, and actionable?

---

## 2. Evaluation Tools

| Tool | Purpose | Usage |
|------|---------|-------|
| **LangSmith** | Production tracing, A/B prompt testing | All LLM calls auto-traced |
| **pytest** | Unit + integration tests | CI pipeline |
| **custom eval harness** | Intent accuracy measurement | `tests/eval/` |

---

## 3. Evaluation Datasets

### 3.1 Intent Classification Dataset
File: `tests/eval/intent_dataset.json`

```json
[
  {
    "id": "IC-001",
    "input": "Create a high priority task for John to deploy the frontend by Friday",
    "expected_intent": "CREATE_TASK",
    "expected_context": {
      "title": "Deploy the frontend",
      "assignee_name": "John",
      "priority": "HIGH",
      "due_date_relative": "Friday"
    }
  },
  {
    "id": "IC-002",
    "input": "Assign API testing to Rahul",
    "expected_intent": "CREATE_TASK",
    "expected_context": {
      "title": "API testing",
      "assignee_name": "Rahul"
    }
  },
  {
    "id": "IC-003",
    "input": "Show my pending tasks",
    "expected_intent": "GET_MY_TASKS",
    "expected_context": { "status": ["TODO", "IN_PROGRESS"] }
  },
  {
    "id": "IC-004",
    "input": "What should I focus on today?",
    "expected_intent": "PLAN_DAY",
    "expected_context": {}
  },
  {
    "id": "IC-005",
    "input": "Mark the CRM deployment task as completed",
    "expected_intent": "COMPLETE_TASK",
    "expected_context": { "title_hint": "CRM deployment" }
  },
  {
    "id": "IC-006",
    "input": "What are my overdue tasks?",
    "expected_intent": "GET_OVERDUE_TASKS",
    "expected_context": {}
  },
  {
    "id": "IC-007",
    "input": "Delete the old login page task",
    "expected_intent": "DELETE_TASK",
    "expected_context": { "title_hint": "old login page" }
  },
  {
    "id": "IC-008",
    "input": "Update the API testing deadline to next Monday",
    "expected_intent": "UPDATE_TASK",
    "expected_context": { "title_hint": "API testing", "due_date_relative": "next Monday" }
  }
]
```

**Target Accuracy**: ≥ 95% on this dataset.

### 3.2 Entity Extraction Dataset
File: `tests/eval/entity_dataset.json`

Evaluates how well the Supervisor extracts structured fields from natural language.

**Metrics**:
- **Priority extraction accuracy**: target ≥ 97%
- **Date parsing accuracy** (relative dates): target ≥ 90%
- **Assignee name extraction**: target ≥ 95%
- **Task title extraction** (semantic quality): human eval

### 3.3 Response Quality Dataset
File: `tests/eval/response_dataset.json`

End-to-end test cases with expected response patterns.

```json
[
  {
    "id": "RQ-001",
    "scenario": "Task created successfully",
    "expected_contains": ["task", "created", "Task #"],
    "expected_not_contains": ["error", "sorry", "I cannot"],
    "max_length": 200
  }
]
```

---

## 4. Automated Evaluation Pipeline

### 4.1 Intent Accuracy Eval
```python
# tests/eval/test_intent_accuracy.py

import pytest
from tests.eval.dataset import load_intent_dataset
from backend.agents.supervisor import classify_intent

@pytest.mark.asyncio
async def test_intent_classification_accuracy():
    dataset = load_intent_dataset()
    correct = 0
    
    for case in dataset:
        result = await classify_intent(case["input"])
        if result.intent == case["expected_intent"]:
            correct += 1
    
    accuracy = correct / len(dataset)
    print(f"Intent accuracy: {accuracy:.2%} ({correct}/{len(dataset)})")
    
    assert accuracy >= 0.95, f"Intent accuracy {accuracy:.2%} below 95% threshold"
```

### 4.2 Tool Call Eval
```python
# tests/eval/test_tool_calls.py
# Verifies agents call the RIGHT tools for given intents

EXPECTED_TOOL_CALLS = {
    "CREATE_TASK": ["create_task"],
    "GET_MY_TASKS": ["get_user_tasks"],
    "PLAN_DAY": ["get_user_tasks", "get_overdue_tasks"],
    "GET_OVERDUE_TASKS": ["get_overdue_tasks"],
}

@pytest.mark.asyncio
async def test_task_agent_calls_correct_tools():
    # Mock DB, invoke agent, assert tool calls
    ...
```

### 4.3 LangSmith Evaluation (Production)
```python
# backend/evaluation/langsmith_eval.py

from langsmith import Client
from langsmith.evaluation import evaluate

client = Client()

def intent_accuracy_evaluator(run, example):
    """Custom evaluator for LangSmith."""
    predicted = run.outputs.get("intent")
    expected = example.outputs.get("intent")
    return {"score": 1.0 if predicted == expected else 0.0}

results = evaluate(
    classify_intent,
    data="orbit-intent-dataset",
    evaluators=[intent_accuracy_evaluator],
    experiment_prefix="intent-v1"
)
```

---

## 5. Metrics Tracked

### 5.1 LLM Performance Metrics (LangSmith)
| Metric | Description | Alert Threshold |
|--------|-------------|-----------------|
| `intent_accuracy` | % correct intent classifications | < 90% |
| `entity_recall` | % entities correctly extracted | < 85% |
| `avg_latency_ms` | Average LLM response time | > 5000ms |
| `token_count` | Tokens per request | > 2000 |
| `error_rate` | % of LLM calls that failed | > 5% |
| `retry_rate` | % of calls needing retry | > 10% |

### 5.2 System Metrics (Prometheus)
| Metric | Description |
|--------|-------------|
| `orbit_webhook_requests_total` | Total webhook calls |
| `orbit_agent_duration_seconds` | End-to-end agent time |
| `orbit_tool_calls_total{tool_name}` | Tool call frequency |
| `orbit_tasks_created_total` | Tasks created via NL |
| `orbit_briefings_sent_total` | Proactive briefings sent |

---

## 6. Regression Testing

After each prompt change:
1. Run intent accuracy eval (`pytest tests/eval/test_intent_accuracy.py`)
2. Compare score against baseline in LangSmith
3. If accuracy drops > 2%, revert prompt change
4. If latency increases > 1s P95, investigate model or prompt

### Prompt Version Tracking
```python
# backend/agents/prompts.py

SUPERVISOR_PROMPT_VERSION = "v3"
SUPERVISOR_SYSTEM_PROMPT = """
# Supervisor Prompt v3
# Changed: Added explicit handling for ambiguous CREATE_TASK vs UPDATE_TASK
...
"""
```

---

## 7. Human Evaluation (Pre-submission)

Before submission, manually evaluate 20 test conversations:

| # | Test Input | Expected | Pass/Fail |
|---|-----------|---------|-----------|
| 1 | "Create a high priority task for John..." | Task created, correct fields | |
| 2 | "Show my pending tasks" | Task list returned | |
| 3 | "What should I focus on today?" | Prioritized plan | |
| 4 | "Mark the CRM task as done" | Fuzzy match + completed | |
| 5 | "Delete the old task" | HITL confirmation sent | |
| 6 | "Assign this to Sarah" (after creating task) | Memory resolved task | |
| 7 | "What are my overdue tasks?" | Overdue list | |
| 8 | "Update API testing deadline to next Monday" | Date resolved, task updated | |
