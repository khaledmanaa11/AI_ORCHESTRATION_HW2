"""LLMRefereeBrain — AI-driven referee brain using Gemini (Phase 7, FR-JU1–JU7)."""
from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

from agent_arena.services.game.debate_state import active_side as get_active_side
from agent_arena.services.game.debate_state import phase as get_phase
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
from agent_arena.shared import LLMCallerMixin
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


class LLMRefereeBrain(LLMCallerMixin, RefereeBrain):
    """LLM-backed referee brain using Gemini."""

    def __init__(self, model_name: str = "gemini-2.5-flash-lite", provider: str = "google"):
        self._model_name = model_name
        self._client = LLMClient(provider=provider)

    def decide(self, context: RefereeContext) -> RefereeDecision:
        if context.request_kind == RequestKind.EVALUATE_TURN:
            return self._evaluate_turn(context)
        return self._render_verdict(context)

    def _evaluate_turn(self, context: RefereeContext) -> RefereeDecision:
        move = context.move or {}
        text: str = move.get("text", "") if isinstance(move, dict) else ""
        state = context.state

        t = state.get("turn_number", 0) + 1
        snap = state.get("rules_snapshot", {})
        r = snap.get("R", 0)
        first_speaker = snap.get("first_speaker", "PRO")
        side = get_active_side(t, first_speaker)
        cur_phase = get_phase(t, r)
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

        pack_keys = {k for k in evidence_pack if k != "pack_id"}
        if not pack_keys:
            return True

        pack_keys_lower = {k.lower(): k for k in pack_keys}

        import re
        potential_tokens = set(re.findall(r"\bdoc[_-]\w+\b", text, re.IGNORECASE))

        cited_ids = set()
        for k in pack_keys:
            if k.lower() in text.lower():
                cited_ids.add(k)

        # If a potential token in text looks like a citation but is NOT in the pack, fail
        for token in potential_tokens:
            if token.lower() not in pack_keys_lower:
                return False

        # If no doc IDs from the pack are cited at all, fail
        if not cited_ids:
            return False

        # For each cited doc ID, check if its content is referenced
        stop_words = {
            "the", "a", "an", "and", "or", "but", "if", "then", "else", "when", "at",
            "by", "from", "for", "with", "about", "against", "between", "into",
            "through", "during", "before", "after", "above", "below", "to", "of",
            "in", "on", "that", "this", "these", "those", "is", "are", "was", "were",
            "be", "been", "being", "have", "has", "had", "do", "does", "did", "will",
            "would", "shall", "should", "can", "could", "may", "might", "must", "us",
            "we", "you", "they", "he", "she", "it", "i", "my", "your", "his", "her",
            "its", "our", "their", "as", "who", "which", "what", "whom", "whose",
            "why", "how"
        }

        for doc_id in cited_ids:
            entry = evidence_pack[doc_id]
            if isinstance(entry, dict):
                content_parts = []
                if "text" in entry:
                    content_parts.append(str(entry["text"]))
                if "title" in entry:
                    content_parts.append(str(entry["title"]))
                if not content_parts:
                    content_parts.append(str(entry))
                content_str = " ".join(content_parts)
            else:
                content_str = str(entry)

            content_words = re.findall(r"\b\w+\b", content_str.lower())
            doc_id_clean = doc_id.lower().replace("_", "").replace("-", "")

            sig_content_words = {
                w for w in content_words
                if w not in stop_words
                and not w.isdigit()
                and w.replace("_", "").replace("-", "") != doc_id_clean
            }

            if not sig_content_words:
                if content_str.lower() not in text.lower():
                    return False
                continue

            text_words = re.findall(r"\b\w+\b", text.lower())
            sig_text_words = {
                w for w in text_words
                if w not in stop_words
                and not w.isdigit()
                and w.replace("_", "").replace("-", "") != doc_id_clean
            }

            overlap = sig_content_words.intersection(sig_text_words)
            if not overlap:
                return False

        return True

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
