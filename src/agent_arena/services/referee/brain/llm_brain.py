"""LLMRefereeBrain — AI-driven referee brain using Gemini (Phase 7, FR-JU1–JU7)."""
from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

from agent_arena.services.referee.brain.base import (
    RefereeBrain,
    RefereeContext,
    RefereeDecision,
    RequestKind,
    aggregate_verdict,
)
from agent_arena.services.referee.brain.judge_prompts import (
    build_rationale_prompt,
    build_tiebreak_prompt,
    build_turn_prompt,
)
from agent_arena.shared.llm_client import LLMClient

logger = logging.getLogger(__name__)


class TurnEvaluationResult(BaseModel):
    tell: str = Field(description="Number-free public acknowledgment of the turn.")
    logic_score: float = Field(ge=0, le=10)
    evidence_score: float = Field(ge=0, le=10)
    rebuttal_score: float = Field(ge=0, le=10)
    persuasion_score: float = Field(ge=0, le=10)


class HolisticTiebreakResult(BaseModel):
    winner: str = Field(description="The winner, exactly 'PRO' or 'CON'.")
    rationale: str = Field(description="Holistic rationale for breaking the tie.")


class HolisticRationaleResult(BaseModel):
    rationale: str = Field(description="Holistic rationale summarizing the debate and verdict.")


class LLMCallerMixin:
    """Mixin for testability. Overridden in unit tests to mock LLM calls."""

    def _generate_json(self, prompt: str, schema: type[BaseModel]) -> BaseModel:
        return self._client.generate_json(prompt, self._model_name, schema)  # type: ignore


class LLMRefereeBrain(LLMCallerMixin, RefereeBrain):
    """LLM-backed referee brain using Gemini."""

    def __init__(self, model_name: str = "gemini-2.5-flash-lite"):
        self._model_name = model_name
        self._client = LLMClient()

    def decide(self, context: RefereeContext) -> RefereeDecision:
        if context.request_kind == RequestKind.EVALUATE_TURN:
            return self._evaluate_turn(context)
        return self._render_verdict(context)

    def _evaluate_turn(self, context: RefereeContext) -> RefereeDecision:
        move = context.move or {}
        text: str = move.get("text", "") if isinstance(move, dict) else ""
        state = context.state

        t = state.get("turn_number", 0)
        side = state.get("active_side", "?")
        cur_phase = state.get("phase", "?")
        variant = context.judge_variant

        prompt = build_turn_prompt(variant, text, side, t, cur_phase, state, context.rubric)
        result: TurnEvaluationResult = self._generate_json(prompt, TurnEvaluationResult)  # type: ignore

        evidence_score = result.evidence_score
        if variant == "structural" and not self._verify_grounding(text, context.evidence_pack):
            evidence_score = 0.0

        turn_scores = {
            "logic": result.logic_score,
            "evidence": evidence_score,
            "rebuttal": result.rebuttal_score,
            "persuasion": result.persuasion_score,
        }

        return RefereeDecision(legal=True, flag=None, tell=result.tell, turn_scores=turn_scores)

    def _verify_grounding(self, text: str, evidence_pack: dict[str, Any]) -> bool:
        """Arm-3 verification. Checks citations traceable to the pack."""
        if not evidence_pack:
            return True
        for doc_id in evidence_pack:
            if doc_id == "pack_id":
                continue
            if str(doc_id) in text:
                return True
        return False

    def _render_verdict(self, context: RefereeContext) -> RefereeDecision:
        rubric = context.rubric or {}
        weights = rubric.get("weights", {"logic": 30.0, "evidence": 30.0, "rebuttal": 25.0, "persuasion": 15.0})

        def _llm_tiebreak(_trajectory: list[dict[str, Any]]) -> str:
            prompt = build_tiebreak_prompt(context.state.get("transcript", []), context.score_trajectory)
            result: HolisticTiebreakResult = self._generate_json(prompt, HolisticTiebreakResult)  # type: ignore
            return result.winner

        verdict = aggregate_verdict(context.score_trajectory, weights, _llm_tiebreak)

        prompt = build_rationale_prompt(verdict, context.state.get("transcript", []), context.score_trajectory)
        rationale_result: HolisticRationaleResult = self._generate_json(prompt, HolisticRationaleResult)  # type: ignore

        verdict["rationale"] = rationale_result.rationale
        return RefereeDecision(legal=True, verdict=verdict)
