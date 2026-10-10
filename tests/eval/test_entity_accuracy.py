"""Accuracy of the offline (rule-based) classifier: the path used with no LLM key and as the
fallback when the LLM fails.

Two datasets are kept apart on purpose:
* entity_dataset.json is the regression set the rules were tuned against.
* entity_holdout.json holds phrasings written afterwards; its score is the honest
  estimate of how the rules cope with wording they have not seen.
The LLM path is expected to generalise better; this suite guards the floor.
"""

import json
from pathlib import Path

import pytest

from agents.intents import Intent
from services.llm import fallback_intent_classifier

EVAL_DIR = Path(__file__).parent
MUTATING = {Intent.CREATE_TASK, Intent.UPDATE_TASK, Intent.DELETE_TASK, Intent.COMPLETE_TASK}


def load(name: str) -> list[dict]:
    return json.loads((EVAL_DIR / name).read_text(encoding="utf-8"))


def check_ctx(result, expected: dict) -> list[str]:
    ctx = result.task_context
    problems = []
    for key, want in expected.items():
        if key == "title_contains":
            got = ctx.title or ""
        elif key == "title_hint_contains":
            got = ctx.title_hint or ""
        else:
            got = getattr(ctx, key) or ""
        matched = want.lower() in got.lower() if key.endswith("_contains") else got.lower() == want.lower()
        if not matched:
            problems.append(f"{key}: expected {want!r}, got {got!r}")
    return problems


def test_regression_set_intent_and_entities():
    cases = load("entity_dataset.json")
    intent_misses, entity_total, entity_misses = [], 0, []
    for case in cases:
        result = fallback_intent_classifier(case["input"])
        if result.intent.value != case["intent"]:
            intent_misses.append(f"{case['id']} {case['input']!r}: {result.intent.value} (want {case['intent']})")
        problems = check_ctx(result, case["ctx"])
        entity_total += len(case["ctx"])
        entity_misses += [f"{case['id']} {p}" for p in problems]

    intent_accuracy = 1 - len(intent_misses) / len(cases)
    entity_accuracy = 1 - len(entity_misses) / max(entity_total, 1)
    print(f"\nregression intent accuracy {intent_accuracy:.1%}, entity accuracy {entity_accuracy:.1%}")
    assert intent_accuracy >= 0.95, "\n".join(intent_misses)
    assert entity_accuracy >= 0.95, "\n".join(entity_misses)


def test_holdout_generalisation_floor():
    cases = load("entity_holdout.json")
    misses = []
    for case in cases:
        got = fallback_intent_classifier(case["input"]).intent.value
        if got != case["intent"]:
            misses.append(f"{case['input']!r}: {got} (want {case['intent']})")
    accuracy = 1 - len(misses) / len(cases)
    print(f"\nholdout intent accuracy {accuracy:.1%} ({len(cases) - len(misses)}/{len(cases)})")
    assert accuracy >= 0.80, "\n".join(misses)


READ_ONLY_REQUESTS = [
    "show me everything assigned to me",
    "what tasks are assigned to John",
    "which tasks were created yesterday",
    "show tasks I'm behind on",
    "who created the deployment task",
    "what did Sarah finish this week",
    "list all tasks that were completed",
    "how many tasks are done",
    "what is the status of the payment task",
    "can you show me my open tasks",
    "tell me about the tasks assigned to Rahul",
]


@pytest.mark.parametrize("text", READ_ONLY_REQUESTS)
def test_questions_are_never_classified_as_changes(text):
    """A wrong read is a nuisance; a wrong write creates, edits, completes or deletes real data."""
    intent = fallback_intent_classifier(text).intent
    assert intent not in MUTATING, f"{text!r} was classified as {intent.value}"


def test_unrecognised_text_is_unknown_not_a_guess():
    for text in ["", "   ", "asdf", "tell me a joke", "thanks!", "ok"]:
        assert fallback_intent_classifier(text).intent == Intent.UNKNOWN, text
