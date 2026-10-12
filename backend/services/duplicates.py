"""Duplicate-task detection: is this new task the same as one that already exists?

Two titles are compared by their meaningful words, not their characters ("Q3 budget" and "Q4 budget"
share a lot of letters but are different tasks). Filler words are ignored, plurals are folded, and a
typo in a longer word is forgiven ("contarct" matches "contract").
"""

import re
from difflib import SequenceMatcher
from typing import Any, Iterable

SIMILAR = 0.75  # worth a heads-up
SAME = 0.92  # the same task, worded differently

_STOPWORDS = frozenset(
    "the a an to for of and on in at with please my our this that it by from up out as is be do i me we you "
    "task tasks new".split()
)
_FUZZY_MIN_LENGTH = 5  # shorter words must match exactly ("q3" is not "q4")
_FUZZY_RATIO = 0.85


def words(title: str) -> list[str]:
    """Meaningful words of a title: lowercase, no punctuation, no filler, plurals folded."""
    tokens = re.findall(r"[a-z0-9]+", (title or "").lower())
    out = []
    for token in tokens:
        if token in _STOPWORDS:
            continue
        if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
            token = token[:-1]
        out.append(token)
    return out


def _same_word(a: str, b: str) -> bool:
    if a == b:
        return True
    return min(len(a), len(b)) >= _FUZZY_MIN_LENGTH and SequenceMatcher(None, a, b).ratio() >= _FUZZY_RATIO


def similarity(a: str, b: str) -> float:
    """0.0 (unrelated) to 1.0 (the same task)."""
    wa, wb = words(a), words(b)
    if not wa or not wb:
        return 0.0
    # one-to-one matching of words
    remaining = list(wb)
    matched = 0
    for word in wa:
        for i, other in enumerate(remaining):
            if _same_word(word, other):
                matched += 1
                del remaining[i]
                break
    if matched == len(wa) == len(wb):
        return 1.0
    score = matched / (len(wa) + len(wb) - matched)
    smaller = min(len(wa), len(wb))
    if smaller >= 2 and matched == smaller:
        score = max(score, 0.85)  # one title is fully contained in the other
    return score


def _title_of(item: Any) -> str:
    return str(item["title"] if isinstance(item, dict) else getattr(item, "title", ""))


def find_similar(title: str, candidates: Iterable[Any], threshold: float = SIMILAR, limit: int = 3) -> list[tuple[float, Any]]:
    """The best matches among `candidates` (dicts with a "title", or objects with a .title), best first."""
    scored = [(similarity(title, _title_of(item)), item) for item in candidates]
    kept = [(score, item) for score, item in scored if score >= threshold]
    kept.sort(key=lambda pair: -pair[0])
    return kept[:limit]
