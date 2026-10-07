"""Intent Classification Accuracy Evaluation Suite."""

import json
from pathlib import Path
import pytest
from agents.supervisor import classify_intent


def load_intent_dataset():
    """Loads intent evaluation test set."""
    dataset_path = Path(__file__).parent / "intent_dataset.json"
    with open(dataset_path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.mark.asyncio
async def test_intent_classification_accuracy():
    """Evaluates accuracy of intent classification against benchmark dataset."""
    dataset = load_intent_dataset()
    correct = 0

    for case in dataset:
        result = await classify_intent(case["input"])
        matched = result.intent == case["expected_intent"]
        if matched:
            correct += 1

    accuracy = correct / len(dataset)
    print(f"\nIntent accuracy: {accuracy:.2%} ({correct}/{len(dataset)})")
    assert accuracy >= 0.85, f"Intent accuracy {accuracy:.2%} below threshold"
