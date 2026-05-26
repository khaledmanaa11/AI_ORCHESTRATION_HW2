"""Tests for the LLM-backed referee brain (Module I)."""
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
    """Mock subclass to intercept _generate_json."""
    def __init__(self):
        self._model_name = "mock-model"
        self._client = None
        self.calls = []
        self.mock_eval_result = TurnEvaluationResult(
            tell="Mock tell",
            logic_score=8.0,
            evidence_score=9.0,
            rebuttal_score=7.0,
            persuasion_score=8.5,
        )
        self.mock_tiebreak_result = HolisticTiebreakResult(
            winner="PRO",
            rationale="Mock tiebreak rationale"
        )
        self.mock_rationale_result = HolisticRationaleResult(
            rationale="Mock holistic rationale"
        )

    def _generate_json(self, prompt: str, schema: type[BaseModel]) -> BaseModel:
        self.calls.append((prompt, schema))
        if schema == TurnEvaluationResult:
            return self.mock_eval_result
        if schema == HolisticTiebreakResult:
            return self.mock_tiebreak_result
        if schema == HolisticRationaleResult:
            return self.mock_rationale_result
        raise ValueError(f"Unexpected schema {schema}")


@pytest.fixture
def base_context():
    return RefereeContext(
        request_kind=RequestKind.EVALUATE_TURN,
        state={"turn_number": 1, "active_side": "PRO", "phase": "rebuttal"},
        move={"text": "This is a test utterance citing doc_A."},
        rubric={"weights": {"logic": 30, "evidence": 30, "rebuttal": 25, "persuasion": 15}},
        judge_variant="naive",
        evidence_pack={"doc_A": "Test evidence content."},
        score_trajectory=[],
    )

def test_evaluate_turn_parsing(base_context):
    brain = MockLLMRefereeBrain()
    decision = brain.decide(base_context)

    assert decision.legal is True
    assert decision.tell == "Mock tell"
    assert decision.turn_scores == {
        "logic": 8.0,
        "evidence": 9.0,
        "rebuttal": 7.0,
        "persuasion": 8.5,
    }
    assert len(brain.calls) == 1

def test_prompt_selection(base_context):
    brain = MockLLMRefereeBrain()

    # Naive
    base_context.judge_variant = "naive"
    brain.decide(base_context)
    assert "Apply rubric straight" in brain.calls[-1][0]

    # Hardened
    base_context.judge_variant = "hardened"
    brain.decide(base_context)
    assert "discount unverifiable claims" in brain.calls[-1][0].lower()

    # Structural
    base_context.judge_variant = "structural"
    brain.decide(base_context)
    assert "focus on argument forms" in brain.calls[-1][0].lower()

def test_arm3_grounding(base_context):
    brain = MockLLMRefereeBrain()
    base_context.judge_variant = "structural"

    # Has citation -> Evidence score remains
    decision = brain.decide(base_context)
    assert decision.turn_scores["evidence"] == 9.0

    # Missing citation -> Evidence score zeroed
    base_context.move["text"] = "No citations here."
    decision2 = brain.decide(base_context)
    assert decision2.turn_scores["evidence"] == 0.0

def test_render_verdict(base_context):
    brain = MockLLMRefereeBrain()
    base_context.request_kind = RequestKind.RENDER_VERDICT
    base_context.score_trajectory = [
        {"side": "PRO", "turn_scores": {"logic": 10, "evidence": 10, "rebuttal": 10, "persuasion": 10}},
        {"side": "CON", "turn_scores": {"logic": 5, "evidence": 5, "rebuttal": 5, "persuasion": 5}},
    ]

    decision = brain.decide(base_context)
    assert decision.legal is True
    verdict = decision.verdict
    assert verdict["winner"] == "PRO"
    assert verdict["rationale"] == "Mock holistic rationale"

    # Check that it called _generate_json for rationale
    assert any(schema == HolisticRationaleResult for prompt, schema in brain.calls)

def test_tiebreak(base_context):
    brain = MockLLMRefereeBrain()
    base_context.request_kind = RequestKind.RENDER_VERDICT
    # Tie trajectory
    base_context.score_trajectory = [
        {"side": "PRO", "turn_scores": {"logic": 10, "evidence": 10, "rebuttal": 10, "persuasion": 10}},
        {"side": "CON", "turn_scores": {"logic": 10, "evidence": 10, "rebuttal": 10, "persuasion": 10}},
    ]
    decision = brain.decide(base_context)
    verdict = decision.verdict
    assert verdict["winner"] == "PRO" # from mock tiebreak

    # Should have called tiebreak and rationale
    schemas = [schema for prompt, schema in brain.calls]
    assert HolisticTiebreakResult in schemas
    assert HolisticRationaleResult in schemas
