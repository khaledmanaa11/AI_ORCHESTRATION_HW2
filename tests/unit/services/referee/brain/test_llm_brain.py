"""Tests for LLM referee brain (Module I)."""
from __future__ import annotations

import pytest
from pydantic import BaseModel

from agent_arena.services.referee.brain.base import RefereeContext, RequestKind
from agent_arena.services.referee.brain.llm_brain import (
    HolisticRationaleResult,
    HolisticTiebreakResult,
    LLMRefereeBrain,
    TurnEvaluationResult,
)


class MockLLMRefereeBrain(LLMRefereeBrain):
    def __init__(self) -> None:
        self._model_name, self._client, self.calls = "mock-model", None, []
        self.mock_eval = TurnEvaluationResult(tell="M tell", logic_score=8, evidence_score=9, rebuttal_score=7, persuasion_score=8.5)
        self.mock_tie = HolisticTiebreakResult(winner="PRO", rationale="M tie")
        self.mock_rat = HolisticRationaleResult(rationale="M rat")

    def _generate_json(self, prompt: str, schema: type[BaseModel]) -> BaseModel:
        self.calls.append((prompt, schema))
        return {TurnEvaluationResult: self.mock_eval, HolisticTiebreakResult: self.mock_tie, HolisticRationaleResult: self.mock_rat}[schema]

@pytest.fixture
def base_context() -> RefereeContext:
    return RefereeContext(
        request_kind=RequestKind.EVALUATE_TURN,
        state={"motion": "Test motion on global warming", "turn_number": 1, "active_side": "PRO", "phase": "OPENING", "rules_snapshot": {"word_cap": 250}, "transcript": []},
        move={"text": "This is a test utterance citing doc_A."},
        rubric={"criteria": ["logic", "evidence", "rebuttal", "persuasion"], "weights": {"logic": 30, "evidence": 30, "rebuttal": 25, "persuasion": 15}},
        judge_variant="naive", evidence_pack={"doc_A": "Test content."}, score_trajectory=[]
    )

def test_evaluate_turn_parsing(base_context: RefereeContext) -> None:
    brain = MockLLMRefereeBrain()
    decision = brain.decide(base_context)
    assert decision.legal is True and decision.tell == "M tell"
    assert decision.turn_scores == {"logic": 8, "evidence": 9, "rebuttal": 7, "persuasion": 8.5}

def test_prompt_selection(base_context: RefereeContext) -> None:
    brain = MockLLMRefereeBrain()
    # Naive
    base_context.judge_variant = "naive"
    brain.decide(base_context)
    prompt_naive = brain.calls[-1][0]
    assert "Apply the rubric straight" in prompt_naive
    # Hardened
    base_context.judge_variant = "hardened"
    brain.decide(base_context)
    prompt_hardened = brain.calls[-1][0]
    assert "bias warnings" in prompt_hardened.lower() and "discount unverifiable" in prompt_hardened.lower()
    # Structural
    base_context.judge_variant = "structural"
    brain.decide(base_context)
    prompt_structural = brain.calls[-1][0]
    assert "bias warnings" in prompt_structural.lower() and "cite the shared evidence pack" in prompt_structural.lower()
    assert prompt_naive != prompt_hardened != prompt_structural != prompt_naive

def test_evaluate_turn_prompt_contents(base_context: RefereeContext) -> None:
    brain = MockLLMRefereeBrain()
    brain.decide(base_context)
    p = brain.calls[-1][0]
    assert all(x in p.lower() for x in ["test motion on global warming", "logic", "evidence", "rebuttal", "persuasion", "0-10", "250"])

def test_rebuttal_opponent_prior(base_context: RefereeContext) -> None:
    brain = MockLLMRefereeBrain()
    base_context.state["phase"] = "REBUTTAL"
    base_context.state["transcript"] = [{"turn_number": 1, "side": "PRO", "utterance": "Pro opponent initial view."}]
    brain.decide(base_context)
    assert "Pro opponent initial view." in brain.calls[-1][0]

def test_arm3_grounding(base_context: RefereeContext) -> None:
    brain = MockLLMRefereeBrain()
    base_context.judge_variant = "structural"
    assert brain.decide(base_context).turn_scores["evidence"] == 9.0
    base_context.move = {"text": "No citations."}
    assert brain.decide(base_context).turn_scores["evidence"] == 0.0

def test_render_verdict(base_context: RefereeContext) -> None:
    brain = MockLLMRefereeBrain()
    base_context.request_kind = RequestKind.RENDER_VERDICT
    base_context.state["transcript"] = [{"turn_number": 1, "side": "PRO", "utterance": "Some transcript speech PRO"}]
    base_context.score_trajectory = [{"side": "PRO", "turn_scores": {"logic": 10, "evidence": 10, "rebuttal": 10, "persuasion": 10}}]
    decision = brain.decide(base_context)
    assert decision.verdict["winner"] == "PRO" and decision.verdict["rationale"] == "M rat"
    p = [c[0] for c in brain.calls if c[1] == HolisticRationaleResult][0]
    assert "Some transcript speech PRO" in p and "score trajectory" in p.lower()

def test_tiebreak(base_context: RefereeContext) -> None:
    brain = MockLLMRefereeBrain()
    base_context.request_kind = RequestKind.RENDER_VERDICT
    base_context.state["transcript"] = [{"turn_number": 1, "side": "PRO", "utterance": "Tie PRO"}, {"turn_number": 2, "side": "CON", "utterance": "Tie CON"}]
    base_context.score_trajectory = [
        {"side": "PRO", "turn_scores": {"logic": 10, "evidence": 10, "rebuttal": 10, "persuasion": 10}},
        {"side": "CON", "turn_scores": {"logic": 10, "evidence": 10, "rebuttal": 10, "persuasion": 10}}
    ]
    assert brain.decide(base_context).verdict["winner"] == "PRO"
    p = [c[0] for c in brain.calls if c[1] == HolisticTiebreakResult][0]
    assert "Tie PRO" in p and "Tie CON" in p
