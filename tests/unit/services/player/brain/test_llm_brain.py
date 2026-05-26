"""Unit tests for LLMPlayerBrain (Module P5, RP5.1-RP5.4)."""
from __future__ import annotations

import json

from agent_arena.services.player.brain.base import PlayerContext, PlayerDecision
from agent_arena.services.player.brain.llm_brain import LLMPlayerBrain, _get_val


class SimpleObject:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


def test_get_val_helper() -> None:
    """Test the _get_val helper function to ensure full branch coverage."""
    # Test dictionary path
    d = {"a": {"b": 1}}
    assert _get_val(d, ["a", "b"], None) == 1
    assert _get_val(d, ["a", "c"], 2) == 2

    # Test object attribute path
    obj = SimpleObject(a=SimpleObject(b=10))
    assert _get_val(obj, ["a", "b"], None) == 10
    assert _get_val(obj, ["a", "c"], 20) == 20

    # Test None / missing path handling
    assert _get_val(None, ["a"], "default") == "default"
    assert _get_val(d, ["a", "b", "c"], "default") == "default"



class FakeLLMClient:
    """Fake LLM client counting calls and returning canned responses."""

    def __init__(self, response_text: str) -> None:
        self.calls: list[tuple[str, str]] = []
        self.response_text = response_text

    def generate_text(self, prompt: str, model_name: str) -> str:
        self.calls.append((prompt, model_name))
        return self.response_text


def test_llm_player_brain_one_call_and_trace_shape() -> None:
    """Verify exactly one call occurs, trace matches the requirement, and configuration is read."""
    response_data = {
        "read_profile": {
            "revealed_criterion_emphasis": "logic and evidence",
            "style_notes": "academic diction",
            "susceptibility": {"sycophancy": 0.8, "authority": 0.2}
        },
        "reflexion_lesson": "Use more logic next time",
        "candidate_drafts": [
            {"text": "Draft 1: neutral text.", "targets": []},
            {"text": "Draft 2: therefore we must conclude logic is clear.", "targets": ["sycophancy"]}
        ]
    }
    client = FakeLLMClient(json.dumps(response_data))

    config = {
        "llm": {
            "model_name": "custom-gemini-model"
        },
        "debate": {
            "player": {
                "best_of_N": 2,
                "temperature": 0.8,
                "top_p": 0.95,
                "selector_weights": {"sycophancy": 10.0}
            }
        }
    }

    brain = LLMPlayerBrain(client=client, config=config)  # type: ignore[arg-type]

    context = PlayerContext(
        state={"match_id": "test-match-123", "turn_number": 3, "phase": "REBUTTAL"},
        legal_moves=[],
        rubric={"weights": {"logic": 30.0, "evidence": 30.0, "rebuttal": 25.0, "persuasion": 15.0}},
        evidence_pack={},
        side="CON",
        ablation={
            "master": True,
            "vectors": {
                "sycophancy": True,
                "bestN_judge_select": True
            },
            "ablation_cell": "cell-456"
        },
        scratchpad=["prior-lesson-1"],
        seed=12345
    )

    decision = brain.generate(context)

    # 1. Exactly one client call occurs
    assert len(client.calls) == 1
    prompt_sent, model_used = client.calls[0]
    assert model_used == "custom-gemini-model"
    assert "You are a debater on side: CON" in prompt_sent
    assert "prior-lesson-1" in prompt_sent

    # 2. Check move shape
    assert isinstance(decision, PlayerDecision)
    assert isinstance(decision.move, dict)
    assert list(decision.move.keys()) == ["text"]
    assert decision.move["text"] == "Draft 2: therefore we must conclude logic is clear."

    # 3. Check trace shape (FR-PC1 fields)
    trace = decision.trace
    assert trace["match_id"] == "test-match-123"
    assert trace["seed"] == 12345
    assert trace["turn_number"] == 3
    assert trace["side"] == "CON"
    assert trace["phase"] == "REBUTTAL"
    assert trace["read_profile"] == response_data["read_profile"]
    assert trace["selected_vectors"] == ["sycophancy"]
    assert trace["candidate_drafts"] == response_data["candidate_drafts"]
    assert trace["selected_draft_index"] == 1
    assert trace["reflexion_lesson"] == "Use more logic next time"
    assert trace["ablation_cell"] == "cell-456"


def test_llm_player_brain_is_stateless() -> None:
    """Verify that LLMPlayerBrain remains stateless between calls."""
    response_data = {
        "read_profile": {},
        "reflexion_lesson": "No lesson",
        "candidate_drafts": [{"text": "Hello", "targets": []}]
    }
    client = FakeLLMClient(json.dumps(response_data))
    config = {
        "llm": {"model_name": "gemini-2.0-flash"},
        "debate": {"player": {"best_of_N": 1}}
    }
    brain = LLMPlayerBrain(client=client, config=config)  # type: ignore[arg-type]

    # Verify no mutable match/stateful instance attributes exist
    initial_attrs = set(dir(brain))

    context1 = PlayerContext(
        state={"match_id": "match-1", "turn_number": 1, "phase": "OPENING"},
        legal_moves=[],
        rubric={},
        evidence_pack={},
        side="PRO",
        ablation={},
        scratchpad=[],
        seed=1
    )
    _ = brain.generate(context1)

    context2 = PlayerContext(
        state={"match_id": "match-2", "turn_number": 2, "phase": "REBUTTAL"},
        legal_moves=[],
        rubric={},
        evidence_pack={},
        side="CON",
        ablation={},
        scratchpad=[],
        seed=2
    )
    _ = brain.generate(context2)

    # Re-verify that the attributes list is unchanged and no match state was stored on self
    final_attrs = set(dir(brain))
    assert initial_attrs == final_attrs
    # Check that brain holds only client and config
    assert brain._client is client
    assert brain._config is config
