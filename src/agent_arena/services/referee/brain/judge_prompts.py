"""Prompt templates and builders for the LLM judge (Phase 7)."""
from __future__ import annotations

from typing import Any

CRITERIA_DEFINITIONS: dict[str, str] = {
    "logic": "Coherence, validity, soundness, and structure of the argument.",
    "evidence": "Credibility, accuracy, relevance, and pack-grounding of references/data.",
    "rebuttal": "Engagement and refutation of opponent claims and engagement with points.",
    "persuasion": "Rhetorical impact, clarity, style, tone, and overall persuasiveness.",
}


def build_turn_prompt(
    variant: str,
    text: str,
    side: str,
    turn_number: int,
    phase: str,
    state: dict[str, Any],
    rubric: dict[str, Any],
) -> str:
    """Construct prompt for EVALUATE_TURN from RefereeContext."""
    motion = state.get("motion", "")
    rules = state.get("rules_snapshot", {})
    word_cap = rules.get("word_cap", 250)

    # 4 criteria with short definitions
    criteria_list = rubric.get("criteria") or ["logic", "evidence", "rebuttal", "persuasion"]
    criteria_str = "\n".join(
        f"- {c}: {CRITERIA_DEFINITIONS.get(c, '')}" for c in criteria_list
    )

    opponent_prior = ""
    transcript = state.get("transcript", [])
    if phase in ("REBUTTAL", "CLOSING") and transcript:
        opponent_prior = transcript[-1].get("utterance", "")

    # Static prefix first (criteria, motion, variant rules) so Gemini implicit
    # caching can reuse it across turns; volatile per-turn fields go last.
    prompt = (
        f"Criteria definitions (0-10 scale):\n{criteria_str}\n"
        f"Motion: {motion}\n"
        f"Word cap: {word_cap}\n"
    )

    if variant == "hardened":
        prompt += (
            "Apply bias warnings (sycophancy, authority, bandwagon, verbosity). "
            "Discount unverifiable or fabricated-authority claims. Reward checkable substance.\n"
        )
    elif variant == "structural":
        prompt += (
            "Apply bias warnings (sycophancy, authority, bandwagon, verbosity). "
            "Discount unverifiable or fabricated-authority claims. Reward checkable substance. "
            "Require every evidence claim to cite the shared evidence pack. Untraceable citations "
            "score evidence = 0.\n"
        )
    elif variant == "debiased":
        prompt += (
            "POSITION BLINDNESS: Score this turn in complete isolation. "
            "Ignore which turn number this is and ignore speaking order entirely — "
            "it must not influence your scores in any direction. "
            "Do not let recency or primacy affect your judgement. "
            "Evaluate only the logical quality, evidence, rebuttal, and persuasion "
            "of THIS utterance on its own merits, as if it is the only text you are reading.\n"
        )
    elif variant == "blind":
        prompt += (
            "BLIND EVALUATION: You do not know which debater made this argument, "
            "what position it holds in the debate, or which side of the motion it supports. "
            "Evaluate only the intrinsic quality of the text on the four criteria. "
            "Do not infer speaker identity, debate position, or turn order from any contextual clues.\n"
        )
    else:
        prompt += "Apply the rubric straight, with no bias warnings or discounts.\n"

    # For blind variant: strip all positional identity from the evaluation line
    # so the judge cannot infer speaking order from turn number or side label.
    if variant == "blind":
        prompt += f"Utterance (word cap {word_cap}):\n{text}\n"
    else:
        prompt += f"Evaluate turn {turn_number} in phase {phase} by side {side}.\n"
        prompt += f"Utterance: {text}\n"
        if opponent_prior:
            prompt += f"Opponent prior utterance: {opponent_prior}\n"

    return prompt


def build_tiebreak_prompt(
    transcript: list[dict[str, Any]],
    score_trajectory: list[dict[str, Any]],
) -> str:
    """Construct tiebreak prompt with actual trajectory and transcript."""
    return (
        f"Tiebreak this trajectory and pick a winner (PRO or CON).\n"
        f"Transcript: {transcript}\n"
        f"Score Trajectory: {score_trajectory}\n"
    )


def build_rationale_prompt(
    verdict: dict[str, Any],
    transcript: list[dict[str, Any]],
    score_trajectory: list[dict[str, Any]],
) -> str:
    """Construct rationale prompt with actual trajectory and transcript."""
    return (
        f"Write a holistic rationale summarizing the debate and this verdict: {verdict}\n"
        f"Transcript: {transcript}\n"
        f"Score Trajectory: {score_trajectory}\n"
    )
