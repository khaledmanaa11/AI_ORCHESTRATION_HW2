"""Tests for the debate config block — Module G (RG3.1)."""
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from agent_arena.shared.config import (
    DebateConfig,
    DebateJudgeConfig,
    DebateMatchConfig,
    load_setup_config,
)


def _full_config(*, debate_override: dict | None = None) -> dict:
    """Return a complete setup.json dict; optionally patch the debate block."""
    base = {
        "version": "1.00",
        "network": {"host": "127.0.0.1", "port": 9000},
        "game": {"move_timeout_seconds": 10.0},
        "framing": {"max_frame_size_bytes": 10485760},
        "llm": {"model_name": "claude-opus-4-5"},
        "debate": {
            "format": {"rebuttal_rounds": 3, "word_cap": 250,
                       "first_speaker": "PRO", "retry_cap": 1},
            "judge": {"variant": "naive",
                      "weights": {"logic": 30, "evidence": 30,
                                  "rebuttal": 25, "persuasion": 15}},
            "player": {"best_of_N": 3, "private_capture": True,
                       "ablation": {"master": False, "vectors": {},
                                    "baseline_mode": "beta"}},
            "match": {"motion": "AI is beneficial",
                      "evidence_pack": "pack_001", "seed": 42},
        },
    }
    if debate_override is not None:
        base["debate"] = debate_override
    return base


def _write(tmp_path: Path, data: dict) -> Path:
    p = tmp_path / "setup.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


# ── RG3.1 — debate block loads without error ─────────────────────────

def test_load_debate_block_from_file(tmp_path: Path) -> None:
    cfg = load_setup_config(_write(tmp_path, _full_config()))
    assert cfg.debate is not None
    assert cfg.debate.format.rebuttal_rounds == 3


def test_load_real_setup_json() -> None:
    """Load the actual config/setup.json shipped in the repo."""
    cfg = load_setup_config(Path("config/setup.json"))
    assert cfg.debate.format.rebuttal_rounds == 3
    assert cfg.debate.match.seed == 42


# ── Weights validation ───────────────────────────────────────────────

def test_weights_sum_not_100_raises() -> None:
    bad = {"logic": 50, "evidence": 30, "rebuttal": 25, "persuasion": 15}
    with pytest.raises(ValidationError, match="judge weights must sum to 100"):
        DebateJudgeConfig(variant="naive", weights=bad)


def test_weights_sum_100_passes() -> None:
    good = {"logic": 30, "evidence": 30, "rebuttal": 25, "persuasion": 15}
    cfg = DebateJudgeConfig(variant="naive", weights=good)
    assert sum(cfg.weights.values()) == 100


# ── Variant validation ──────────────────────────────────────────────

def test_unknown_variant_raises() -> None:
    with pytest.raises(ValidationError, match="unknown judge variant"):
        DebateJudgeConfig(variant="random_thing")


def test_valid_variants() -> None:
    for v in ("naive", "hardened", "structural"):
        cfg = DebateJudgeConfig(variant=v)
        assert cfg.variant == v


# ── Type checks ──────────────────────────────────────────────────────

def test_match_seed_is_int() -> None:
    m = DebateMatchConfig(motion="x", evidence_pack="y", seed=42)
    assert isinstance(m.seed, int)


def test_format_rebuttal_rounds_default() -> None:
    cfg = DebateConfig(match=DebateMatchConfig(motion="x", evidence_pack="y", seed=1))
    assert cfg.format.rebuttal_rounds == 3
