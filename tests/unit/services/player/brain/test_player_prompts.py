import pytest

from agent_arena.services.player.brain.base import PlayerContext
from agent_arena.services.player.brain.constants import (
    VECTOR_ADAPTIVE_PERSONA,
    VECTOR_AUTHORITY,
    VECTOR_BANDWAGON,
    VECTOR_FALLACY,
    VECTOR_READ_TARGETING,
    VECTOR_SYCOPHANCY,
)
from agent_arena.services.player.brain.player_prompts import build_player_prompt


@pytest.fixture
def base_context():
    return PlayerContext(
        state={
            "motion": "AI should be regulated.",
            "phase": "OPENING",
            "turn_number": 1,
            "transcript": [
                {
                    "turn_number": 1,
                    "side": "PRO",
                    "phase": "OPENING",
                    "utterance": "AI improves diagnostic speed.",
                    "referee_tell": "Strong evidence focus.",
                    "referee_flag": None,
                }
            ],
            "rules_snapshot": {
                "word_cap": 200,
                "must_engage": True,
            },
        },
        legal_moves=[
            {
                "turn_number": 2,
                "side": "CON",
                "phase": "OPENING",
                "word_cap": 180,
                "must_engage": False,
            }
        ],
        rubric={"criteria": ["logic"], "weights": {"logic": 100}},
        evidence_pack={"DOC-001": "some data"},
        side="PRO",
        ablation={"master": False, "baseline_mode": "beta", "vectors": {}},
        scratchpad=["lesson1"],
        seed=42,
    )


@pytest.fixture
def base_config():
    return {
        "debate": {
            "player": {
                "best_of_N": 4,
                "temperature": 0.8,
                "top_p": 0.95,
            }
        }
    }


def test_generation_params_sourced_from_config(base_context, base_config):
    _, params = build_player_prompt(base_context, base_config)
    assert params["temperature"] == 0.8
    assert params["top_p"] == 0.95
    assert params["seed"] == 42


def test_output_schema_requests_json_and_drafts(base_context, base_config):
    prompt_str, _ = build_player_prompt(base_context, base_config)
    assert "read_profile" in prompt_str
    assert "reflexion_lesson" in prompt_str
    assert "candidate_drafts" in prompt_str
    assert "generate exactly 4 drafts" in prompt_str


def test_prompt_includes_public_transcript_and_legal_move(base_context, base_config):
    prompt_str, _ = build_player_prompt(base_context, base_config)
    assert "Turn: 2" in prompt_str
    assert "word cap 180" in prompt_str
    assert "must-engage opponent: False" in prompt_str
    assert "AI improves diagnostic speed." in prompt_str
    assert "Strong evidence focus." in prompt_str


def test_off_roster_contains_no_control_vocabulary(base_context, base_config):
    # OFF-roster branch (master=False)
    prompt_str, _ = build_player_prompt(base_context, base_config)

    # Check that control vocabulary / vector names are absent from instructions
    control_words = [
        "sycophancy", "authority", "bandwagon", "fallacy", "adaptive persona", "read-targeting"
    ]
    for word in control_words:
        assert word not in prompt_str.lower()

    assert "tells adaptation" in prompt_str.lower()
    assert "do not attempt any manipulation" in prompt_str.lower()


def test_on_roster_contains_control_vocabulary_and_gated_vectors(base_context, base_config):
    # ON-roster branch (master=True) with all vectors enabled
    ablation = {
        "master": True,
        "vectors": {
            VECTOR_SYCOPHANCY: True,
            VECTOR_AUTHORITY: True,
            VECTOR_BANDWAGON: True,
            VECTOR_FALLACY: True,
            VECTOR_ADAPTIVE_PERSONA: True,
            VECTOR_READ_TARGETING: True,
        }
    }
    context = PlayerContext(
        state=base_context.state,
        legal_moves=base_context.legal_moves,
        rubric=base_context.rubric,
        evidence_pack=base_context.evidence_pack,
        side=base_context.side,
        ablation=ablation,
        scratchpad=base_context.scratchpad,
        seed=base_context.seed,
    )

    prompt_str, _ = build_player_prompt(context, base_config)

    control_words = ["sycophancy", "authority", "bandwagon", "fallacy", "adaptive persona", "read-targeting"]
    for word in control_words:
        assert word in prompt_str.lower()


def test_disabled_vector_instruction_is_absent(base_context, base_config):
    # Enable sycophancy, disable authority
    ablation = {
        "master": True,
        "vectors": {
            VECTOR_SYCOPHANCY: True,
            VECTOR_AUTHORITY: False,
        }
    }
    context = PlayerContext(
        state=base_context.state,
        legal_moves=base_context.legal_moves,
        rubric=base_context.rubric,
        evidence_pack=base_context.evidence_pack,
        side=base_context.side,
        ablation=ablation,
        scratchpad=base_context.scratchpad,
        seed=base_context.seed,
    )

    prompt_str, _ = build_player_prompt(context, base_config)
    assert "sycophancy" in prompt_str.lower()
    assert "authority:" not in prompt_str.lower()


def test_alpha_baseline_omits_tell_adaptation(base_context, base_config):
    # baseline_mode = alpha
    ablation = {
        "master": False,
        "baseline_mode": "alpha",
    }
    context = PlayerContext(
        state=base_context.state,
        legal_moves=base_context.legal_moves,
        rubric=base_context.rubric,
        evidence_pack=base_context.evidence_pack,
        side=base_context.side,
        ablation=ablation,
        scratchpad=base_context.scratchpad,
        seed=base_context.seed,
    )

    prompt_str, _ = build_player_prompt(context, base_config)
    assert "tells adaptation" not in prompt_str.lower()


def test_object_config_traversal(base_context):
    class InnerPlayer:
        def __init__(self):
            self.best_of_N = 5
            self.temperature = 0.65
            self.top_p = 0.85

    class InnerDebate:
        def __init__(self):
            self.player = InnerPlayer()

    class MockConfig:
        def __init__(self):
            self.debate = InnerDebate()

    config = MockConfig()
    _, params = build_player_prompt(base_context, config)
    assert params["temperature"] == 0.65
    assert params["top_p"] == 0.85

    # Triggering non-existent attribute
    from agent_arena.services.player.brain.player_prompts import _get_val
    assert _get_val(config, ["debate", "non_existent"], "fallback") == "fallback"
    assert _get_val(config, ["debate", "player", "non_existent"], "fallback") == "fallback"

