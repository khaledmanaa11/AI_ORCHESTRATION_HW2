"""Tests for RefereeBrain ABC, dataclasses, and aggregate_verdict (Module C)."""
from __future__ import annotations

import pytest

from agent_arena.services.referee.brain.base import (
    RefereeBrain,
    RefereeContext,
    RefereeDecision,
    RequestKind,
    aggregate_verdict,
)

WEIGHTS = {"logic": 30.0, "evidence": 30.0, "rebuttal": 25.0, "persuasion": 15.0}


# ---------------------------------------------------------------------------
# RequestKind
# ---------------------------------------------------------------------------


def test_request_kind_values():
    assert RequestKind.EVALUATE_TURN == "evaluate_turn"
    assert RequestKind.RENDER_VERDICT == "render_verdict"


# ---------------------------------------------------------------------------
# ABC cannot be instantiated; trivial subclass works (RC4.1)
# ---------------------------------------------------------------------------


def test_referee_brain_abc_cannot_instantiate():
    with pytest.raises(TypeError):
        RefereeBrain()  # type: ignore[abstract]


def test_trivial_subclass_works():
    class AlwaysLegal(RefereeBrain):
        def decide(self, _context: RefereeContext) -> RefereeDecision:
            return RefereeDecision(legal=True, tell="ok")

    brain = AlwaysLegal()
    ctx = RefereeContext(
        request_kind=RequestKind.EVALUATE_TURN,
        state={},
        move={"text": "hello"},
        rubric={},
        judge_variant="naive",
        evidence_pack={},
        score_trajectory=[],
    )
    decision = brain.decide(ctx)
    assert decision.legal is True
    assert decision.tell == "ok"


# ---------------------------------------------------------------------------
# RefereeDecision defaults
# ---------------------------------------------------------------------------


def test_referee_decision_defaults():
    d = RefereeDecision()
    assert d.legal is True
    assert d.flag is None
    assert d.tell is None
    assert d.turn_scores is None
    assert d.verdict is None


# ---------------------------------------------------------------------------
# aggregate_verdict — hand-computed trajectory (RC4.2)
# ---------------------------------------------------------------------------


def _make_trajectory() -> list[dict]:
    """PRO 5 turns (scores all 8.0), CON 5 turns (scores all 4.0)."""
    items = []
    for _i in range(5):
        items.append({
            "side": "PRO",
            "turn_scores": {"logic": 8.0, "evidence": 8.0, "rebuttal": 8.0, "persuasion": 8.0},
        })
    for _i in range(5):
        items.append({
            "side": "CON",
            "turn_scores": {"logic": 4.0, "evidence": 4.0, "rebuttal": 4.0, "persuasion": 4.0},
        })
    return items


def test_aggregate_verdict_winner():
    result = aggregate_verdict(_make_trajectory(), WEIGHTS, lambda _: "PRO")
    assert result["winner"] == "PRO"


def test_aggregate_verdict_margin():
    result = aggregate_verdict(_make_trajectory(), WEIGHTS, lambda _: "PRO")
    # PRO mean per-criterion = 8.0, CON = 4.0; all criteria same → margin = 8.0-4.0 = 4.0
    assert result["margin"] == pytest.approx(4.0, abs=1e-3)


def test_aggregate_verdict_per_criterion_means():
    result = aggregate_verdict(_make_trajectory(), WEIGHTS, lambda _: "PRO")
    for c in ("logic", "evidence", "rebuttal", "persuasion"):
        assert result["scores"]["PRO"][c] == pytest.approx(8.0)
        assert result["scores"]["CON"][c] == pytest.approx(4.0)


def test_aggregate_verdict_weighted_totals():
    result = aggregate_verdict(_make_trajectory(), WEIGHTS, lambda _: "PRO")
    assert result["weighted_totals"]["PRO"] == pytest.approx(8.0, abs=1e-3)
    assert result["weighted_totals"]["CON"] == pytest.approx(4.0, abs=1e-3)


def test_aggregate_verdict_shape_keys():
    result = aggregate_verdict(_make_trajectory(), WEIGHTS, lambda _: "PRO")
    assert set(result.keys()) == {"winner", "margin", "scores", "weighted_totals", "rationale"}


def test_aggregate_verdict_con_wins():
    traj = [
        {"side": "PRO", "turn_scores": {"logic": 3.0, "evidence": 3.0, "rebuttal": 3.0, "persuasion": 3.0}},
        {"side": "CON", "turn_scores": {"logic": 9.0, "evidence": 9.0, "rebuttal": 9.0, "persuasion": 9.0}},
    ]
    result = aggregate_verdict(traj, WEIGHTS, lambda _: "PRO")
    assert result["winner"] == "CON"
    assert result["margin"] < 0


# ---------------------------------------------------------------------------
# aggregate_verdict — total over any trajectory (RC4.3, FR-SB6)
# ---------------------------------------------------------------------------


def test_aggregate_verdict_empty_trajectory():
    result = aggregate_verdict([], WEIGHTS, lambda _: "PRO")
    assert result["winner"] in ("PRO", "CON")
    assert isinstance(result["margin"], float)
    assert "rationale" in result


def test_aggregate_verdict_all_zero_scores():
    traj = [
        {"side": "PRO", "turn_scores": {"logic": 0.0, "evidence": 0.0, "rebuttal": 0.0, "persuasion": 0.0}},
        {"side": "CON", "turn_scores": {"logic": 0.0, "evidence": 0.0, "rebuttal": 0.0, "persuasion": 0.0}},
    ]
    result = aggregate_verdict(traj, WEIGHTS, lambda _: "PRO")
    assert result["winner"] == "PRO"  # tiebreak picks PRO
    assert result["margin"] == pytest.approx(0.0, abs=1e-6)


def test_aggregate_verdict_single_turn():
    traj = [
        {"side": "PRO", "turn_scores": {"logic": 5.0, "evidence": 5.0, "rebuttal": 5.0, "persuasion": 5.0}},
    ]
    result = aggregate_verdict(traj, WEIGHTS, lambda _: "CON")
    # CON has no scores → 0.0 → PRO wins
    assert result["winner"] == "PRO"


def test_aggregate_verdict_never_raises_partial():
    traj = [
        {"side": "PRO", "turn_scores": {}},  # missing criteria → treated as 0
        {"side": "CON"},  # missing turn_scores entirely
    ]
    result = aggregate_verdict(traj, WEIGHTS, lambda _: "PRO")
    assert result["winner"] in ("PRO", "CON")


def test_tiebreak_called_on_exact_tie():
    traj = [
        {"side": "PRO", "turn_scores": {"logic": 5.0, "evidence": 5.0, "rebuttal": 5.0, "persuasion": 5.0}},
        {"side": "CON", "turn_scores": {"logic": 5.0, "evidence": 5.0, "rebuttal": 5.0, "persuasion": 5.0}},
    ]
    called = []

    def tracking_tiebreak(_: list) -> str:
        called.append(True)
        return "CON"

    result = aggregate_verdict(traj, WEIGHTS, tracking_tiebreak)
    assert len(called) == 1
    assert result["winner"] == "CON"
