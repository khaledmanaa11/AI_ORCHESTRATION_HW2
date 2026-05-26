"""Best-of-N Selector (Module P4, BS-2, FR-BN)."""
from __future__ import annotations

from typing import Any


def _get_rubric_quality_score(text: str, rubric_weights: dict[str, float]) -> float:
    """Heuristic scoring based on the rubric criteria and keywords matching."""
    lowered = text.lower()

    # Define keywords for each of the 4 standard criteria
    keywords = {
        "logic": ["therefore", "thus", "consequently", "because", "hence", "logical", "reasoning"],
        "evidence": ["cite", "evidence", "source", "data", "document", "report", "statistics", "study", "doc-"],
        "rebuttal": ["however", "rebut", "opponent", "contradict", "disagree", "refute", "clash"],
        "persuasion": ["clearly", "persuade", "convincingly", "compelling", "vital", "crucial", "must", "essential"],
    }

    score = 0.0
    for criterion, weight in rubric_weights.items():
        criterion_lower = criterion.lower()
        match_count = 0
        if criterion_lower in keywords:
            for kw in keywords[criterion_lower]:
                match_count += lowered.count(kw)
        else:
            match_count += lowered.count(criterion_lower)
        score += float(weight) * match_count

    return score


def pick(
    drafts: list[dict[str, Any]],
    read_profile: dict[str, Any],
    rubric_weights: dict[str, float],
    mode: str,
    selector_weights: dict[str, float],
) -> int:
    """Select the best candidate draft based on the selection mode (RP4.1-RP4.4).

    Ensures tie-breaking is fully deterministic by selecting the lowest draft index.
    """
    if not drafts:
        return 0

    best_index = 0
    best_score = float("-inf")

    susceptibility = read_profile.get("susceptibility", {})
    if not isinstance(susceptibility, dict):
        susceptibility = {}

    for idx, draft in enumerate(drafts):
        text = draft.get("text", "")
        if not isinstance(text, str):
            text = str(text) if text is not None else ""

        # 1. Rubric quality component
        quality_score = _get_rubric_quality_score(text, rubric_weights)

        # 2. Susceptibility weighting component
        exploit_score = 0.0
        if mode == "judge-profile":
            targets = draft.get("targets", [])
            if isinstance(targets, list):
                for vector in targets:
                    v_str = str(vector)
                    sus = float(susceptibility.get(v_str, 0.0))
                    weight = float(selector_weights.get(v_str, 1.0))
                    exploit_score += sus * weight

        score = quality_score + exploit_score

        # Deterministic tie-breaking: strictly greater to prefer lower index
        if score > best_score:
            best_score = score
            best_index = idx

    return best_index
