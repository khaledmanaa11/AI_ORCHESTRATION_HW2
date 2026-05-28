"""Tests for SimpleRefereeBrain (Module D)."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from agent_arena.services.referee.brain.base import (
    RefereeContext,
    RequestKind,
)
from agent_arena.services.referee.brain.simple_brain import (
    CONCESSION_TOKENS,
    SimpleRefereeBrain,
    simple_tiebreak,
)

WEIGHTS = {"logic": 30.0, "evidence": 30.0, "rebuttal": 25.0, "persuasion": 15.0}
RUBRIC = {"weights": WEIGHTS}
WORD_CAP = 250

_MODULE_PATH = Path(__file__).parents[5] / "src" / "agent_arena" / "services" / "referee" / "brain" / "simple_brain.py"


def _make_ctx(
    kind: RequestKind = RequestKind.EVALUATE_TURN,
    text: str = "This is a valid argument.",
    trajectory: list | None = None,
) -> RefereeContext:
    return RefereeContext(
        request_kind=kind,
        state={
            "turn_number": 0,
            "active_side": None,
            "phase": None,
            "rules_snapshot": {"word_cap": WORD_CAP},
        },
        move={"text": text},
        rubric=RUBRIC,
        judge_variant="naive",
        evidence_pack={},
        score_trajectory=trajectory or [],
    )


# ---------------------------------------------------------------------------
# D1 — No-external-call CI guard (R-AC3, FR-SB1)
# ---------------------------------------------------------------------------


def test_no_forbidden_imports_in_simple_brain():
    """Assert simple_brain.py imports none of {anthropic, socket, random, time, open}."""
    source = _MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    forbidden = {"anthropic", "socket", "random", "time", "open"}
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    overlap = forbidden & imported
    assert not overlap, f"Forbidden import(s) found in simple_brain.py: {overlap}"


# ---------------------------------------------------------------------------
# D2 — Concession path (FR-SB2)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("utterance", [
    "I concede the point.",
    "I give up arguing.",
    "You win this debate.",
    "I forfeit my position.",
    "I CONCEDE",  # case-insensitive
])
def test_concession_tokens_detected(utterance: str):
    brain = SimpleRefereeBrain()
    ctx = _make_ctx(text=utterance)
    decision = brain.decide(ctx)
    assert decision.legal is False
    assert decision.flag == "concession"
    assert decision.turn_scores is None


def test_normal_utterance_is_legal():
    brain = SimpleRefereeBrain()
    ctx = _make_ctx(text="Artificial intelligence brings tremendous benefits to society.")
    decision = brain.decide(ctx)
    assert decision.legal is True
    assert decision.flag is None


def test_off_topic_is_legal():
    brain = SimpleRefereeBrain()
    ctx = _make_ctx(text="The weather today is quite sunny and pleasant outside.")
    decision = brain.decide(ctx)
    assert decision.legal is True  # off-topic never flagged (FR-SB2, 9.b)


# ---------------------------------------------------------------------------
# D3 — Tell is number-free (FR-SB3)
# ---------------------------------------------------------------------------


def test_tell_contains_no_numeric_score():
    brain = SimpleRefereeBrain()
    ctx = _make_ctx(text="A solid argument about the benefits of AI.")
    decision = brain.decide(ctx)
    assert decision.tell is not None
    # Tell may contain word count as integer; must NOT contain a score like "7.5"
    import re
    assert not re.search(r"\d+\.\d+", decision.tell), "Tell must not contain decimal scores"


def test_tell_contains_turn_metadata():
    brain = SimpleRefereeBrain()
    ctx = _make_ctx(text="A solid argument.")
    decision = brain.decide(ctx)
    assert "T1" in decision.tell
    assert "PRO" in decision.tell
    assert "OPENING" in decision.tell


def test_tell_side_label_not_swapped():
    """Reproduces the S2 label-swap bug."""
    brain = SimpleRefereeBrain()
    # Simulate state just before Turn 2. The previous turn was 1 (PRO).
    ctx = _make_ctx(text="Turn 2 text.")
    ctx.state["turn_number"] = 1
    ctx.state["active_side"] = "PRO"
    ctx.state["phase"] = "OPENING"
    ctx.state["rules_snapshot"]["first_speaker"] = "PRO"
    decision = brain.decide(ctx)
    assert decision.tell is not None
    # If the bug is present, tell will incorrectly label this as PRO (the previous turn's side)
    # The fix ensures it's correctly labeled as CON (the current turn's side).
    assert "T2" in decision.tell
    assert "CON" in decision.tell


# ---------------------------------------------------------------------------
# D4 — Word-count scores (FR-SB4)
# ---------------------------------------------------------------------------


def test_scores_identical_across_criteria():
    brain = SimpleRefereeBrain()
    ctx = _make_ctx(text="one two three four five")
    decision = brain.decide(ctx)
    ts = decision.turn_scores
    assert ts is not None
    values = list(ts.values())
    assert all(v == values[0] for v in values), "All criteria must have identical scores"


def test_score_at_word_cap_is_ten():
    brain = SimpleRefereeBrain()
    text = " ".join(["word"] * WORD_CAP)
    ctx = _make_ctx(text=text)
    decision = brain.decide(ctx)
    assert decision.turn_scores is not None
    assert decision.turn_scores["logic"] == pytest.approx(10.0)


def test_score_below_cap_is_proportional():
    brain = SimpleRefereeBrain()
    # 125 words out of 250 cap → 5.0
    text = " ".join(["word"] * 125)
    ctx = _make_ctx(text=text)
    decision = brain.decide(ctx)
    assert decision.turn_scores is not None
    assert decision.turn_scores["logic"] == pytest.approx(5.0)


def test_score_zero_for_empty_penalized_turn():
    brain = SimpleRefereeBrain()
    ctx = _make_ctx(text="")
    # Simulate penalized turn: empty text
    ctx.move = {"text": ""}
    ctx.state["rules_snapshot"]["word_cap"] = WORD_CAP
    decision = brain.decide(ctx)
    # empty → triggers empty check in engine, but if text is "" it's a penalized turn
    # SimpleRefereeBrain receives it and must return 0.0 (FR-SB4, 9.d)
    # (concession check: "" has no concession tokens → legal=True, scores=0.0)
    if decision.legal:
        assert decision.turn_scores is not None
        assert decision.turn_scores["logic"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# D5 — RENDER_VERDICT (FR-SB5, FR-SB6)
# ---------------------------------------------------------------------------


def _make_verdict_ctx(trajectory: list) -> RefereeContext:
    return RefereeContext(
        request_kind=RequestKind.RENDER_VERDICT,
        state={},
        move=None,
        rubric=RUBRIC,
        judge_variant="naive",
        evidence_pack={},
        score_trajectory=trajectory,
    )


def test_verdict_has_full_2e_shape():
    brain = SimpleRefereeBrain()
    traj = [
        {"side": "PRO", "turn_scores": {"logic": 8.0, "evidence": 8.0, "rebuttal": 8.0, "persuasion": 8.0}},
        {"side": "CON", "turn_scores": {"logic": 4.0, "evidence": 4.0, "rebuttal": 4.0, "persuasion": 4.0}},
    ]
    decision = brain.decide(_make_verdict_ctx(traj))
    v = decision.verdict
    assert v is not None
    assert set(v.keys()) == {"winner", "margin", "scores", "weighted_totals", "rationale"}
    assert v["winner"] in ("PRO", "CON")


def test_verdict_over_all_zero_trajectory():
    brain = SimpleRefereeBrain()
    traj = [
        {"side": "PRO", "turn_scores": {"logic": 0.0, "evidence": 0.0, "rebuttal": 0.0, "persuasion": 0.0}},
        {"side": "CON", "turn_scores": {"logic": 0.0, "evidence": 0.0, "rebuttal": 0.0, "persuasion": 0.0}},
    ]
    decision = brain.decide(_make_verdict_ctx(traj))
    assert decision.verdict is not None
    assert decision.verdict["winner"] in ("PRO", "CON")


def test_verdict_over_empty_trajectory_never_raises():
    brain = SimpleRefereeBrain()
    decision = brain.decide(_make_verdict_ctx([]))
    assert decision.verdict is not None


# ---------------------------------------------------------------------------
# D6 — Variant/pack ignored (FR-SB7)
# ---------------------------------------------------------------------------


def test_variant_has_no_effect():
    brain = SimpleRefereeBrain()
    text = "A compelling argument for the motion."

    def ctx(variant: str) -> RefereeContext:
        return RefereeContext(
            request_kind=RequestKind.EVALUATE_TURN,
            state={"turn_number": 1, "active_side": "PRO", "phase": "OPENING",
                   "rules_snapshot": {"word_cap": WORD_CAP}},
            move={"text": text},
            rubric=RUBRIC,
            judge_variant=variant,
            evidence_pack={},
            score_trajectory=[],
        )

    d_naive = brain.decide(ctx("naive"))
    d_hardened = brain.decide(ctx("hardened"))
    d_structural = brain.decide(ctx("structural"))
    assert d_naive.turn_scores == d_hardened.turn_scores == d_structural.turn_scores


# ---------------------------------------------------------------------------
# D7 — Determinism (R-AC4, RD7.1)
# ---------------------------------------------------------------------------


def test_determinism_evaluate_turn():
    brain = SimpleRefereeBrain()
    ctx = _make_ctx(text="The evidence clearly shows that AI is beneficial for humanity.")
    d1 = brain.decide(ctx)
    d2 = brain.decide(ctx)
    assert d1.legal == d2.legal
    assert d1.flag == d2.flag
    assert d1.tell == d2.tell
    assert d1.turn_scores == d2.turn_scores


def test_determinism_render_verdict():
    brain = SimpleRefereeBrain()
    traj = [
        {"side": "PRO", "turn_scores": {"logic": 7.0, "evidence": 6.0, "rebuttal": 8.0, "persuasion": 9.0}},
        {"side": "CON", "turn_scores": {"logic": 5.0, "evidence": 7.0, "rebuttal": 6.0, "persuasion": 4.0}},
    ]
    ctx = _make_verdict_ctx(traj)
    v1 = brain.decide(ctx).verdict
    v2 = brain.decide(ctx).verdict
    assert v1 == v2


# ---------------------------------------------------------------------------
# Simple tiebreak
# ---------------------------------------------------------------------------


def test_simple_tiebreak_higher_word_count_wins():
    traj = [
        {"side": "PRO", "word_count": 200},
        {"side": "CON", "word_count": 100},
    ]
    assert simple_tiebreak(traj) == "PRO"


def test_simple_tiebreak_tie_goes_to_pro():
    traj = [
        {"side": "PRO", "word_count": 100},
        {"side": "CON", "word_count": 100},
    ]
    assert simple_tiebreak(traj) == "PRO"


def test_concession_tokens_are_frozen():
    assert isinstance(CONCESSION_TOKENS, frozenset)
