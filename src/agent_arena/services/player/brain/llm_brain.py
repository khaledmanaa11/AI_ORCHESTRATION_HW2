"""LLM player brain implementation (Module P5, FR-PB, FR-PC)."""
from __future__ import annotations

from typing import Any

from agent_arena.services.player.brain.base import PlayerBrain, PlayerContext, PlayerDecision
from agent_arena.services.player.brain.constants import VECTOR_BESTN_JUDGE_SELECT
from agent_arena.services.player.brain.output_parser import parse as parse_output
from agent_arena.services.player.brain.player_prompts import build_player_prompt
from agent_arena.services.player.brain.selector import pick as pick_draft
from agent_arena.shared.llm_client import LLMClient


def _get_val(obj: Any, keys: list[str], default: Any) -> Any:
    """Safely get nested attributes or dictionary keys."""
    curr = obj
    for key in keys:
        if isinstance(curr, dict):
            curr = curr.get(key)
        elif hasattr(curr, key):
            curr = getattr(curr, key)
        else:
            return default
        if curr is None:
            return default
    return curr


class LLMPlayerBrain(PlayerBrain):
    """LLM-backed player brain using the shared LLM client (FR-PB1, FR-PB2)."""

    def __init__(self, client: LLMClient, config: Any) -> None:
        """Initialize the LLM Player Brain with injected client and config."""
        self._client = client
        self._config = config

    def generate(self, context: PlayerContext) -> PlayerDecision:
        """Generate a move decision using LLM call, parser, and selector."""
        # 1. Build prompt
        prompt_str, _ = build_player_prompt(context, self._config)

        # 2. Get LLM model name from config
        model_name = _get_val(self._config, ["llm", "model_name"], "gemini-2.5-flash-lite")

        # 3. Make exactly one LLM call
        raw_output = self._client.generate_text(prompt_str, model_name)

        # 4. Parse the output
        parsed_turn = parse_output(raw_output)

        # 5. Determine selection mode from bestN_judge_select ablation
        ablation = context.ablation or {}
        ablation_vectors = _get_val(ablation, ["vectors"], {})
        best_n_enabled = _get_val(ablation_vectors, [VECTOR_BESTN_JUDGE_SELECT], False)
        # Note: bestN_judge_select is only active if master ablation is True
        master_enabled = _get_val(ablation, ["master"], False)
        mode = "judge-profile" if (master_enabled and best_n_enabled) else "rubric-quality"

        # 6. Read selector weights and rubric weights
        selector_weights = _get_val(self._config, ["debate", "player", "selector_weights"], {})
        # Note: rubric weights are read from context.rubric
        rubric_weights = _get_val(context.rubric, ["weights"], {})
        if not rubric_weights:
            # Fallback if rubric is direct dictionary of weights
            rubric_weights = context.rubric or {}

        # 7. Pick the best candidate draft
        selected_idx = pick_draft(
            drafts=parsed_turn.candidate_drafts,
            read_profile=parsed_turn.read_profile,
            rubric_weights=rubric_weights,
            mode=mode,
            selector_weights=selector_weights,
        )

        chosen_draft = parsed_turn.candidate_drafts[selected_idx]
        chosen_text = chosen_draft.get("text", "")

        # 8. Compute selected_vectors = chosen draft's targets intersected with enabled vectors
        enabled_vectors = set()
        if master_enabled:
            for vec_name, is_enabled in ablation_vectors.items():
                if is_enabled:
                    enabled_vectors.add(vec_name)

        draft_targets = chosen_draft.get("targets", [])
        selected_vectors = [t for t in draft_targets if t in enabled_vectors]

        # 9. Get ablation cell identifier
        ablation_cell = _get_val(ablation, ["ablation_cell"], _get_val(ablation, ["cell"], ""))

        # 10. Assemble the trace
        trace = {
            "match_id": _get_val(context.state, ["match_id"], ""),
            "seed": context.seed,
            "turn_number": _get_val(context.state, ["turn_number"], 0),
            "side": context.side,
            "phase": _get_val(context.state, ["phase"], ""),
            "read_profile": parsed_turn.read_profile,
            "selected_vectors": selected_vectors,
            "candidate_drafts": parsed_turn.candidate_drafts,
            "selected_draft_index": selected_idx,
            "reflexion_lesson": parsed_turn.reflexion_lesson,
            "ablation_cell": ablation_cell,
        }

        return PlayerDecision(
            move={"text": chosen_text},
            trace=trace,
        )
