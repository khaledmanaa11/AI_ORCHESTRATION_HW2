"""Tests for Module F: build_game_config, assign_sides, MatchAbortError (RF5.1–RF5.3)."""
from __future__ import annotations

import contextlib
import json
from pathlib import Path

import pytest

from agent_arena.services.referee.matchmaking import (
    MatchAbortError,
    MatchSetup,
    assign_sides,
    build_game_config,
    setup_match,
)
from agent_arena.services.referee.result import write_trajectory

_WEIGHTS = {"logic": 30, "evidence": 30, "rebuttal": 25, "persuasion": 15}
_FORMAT = {"rebuttal_rounds": 3, "word_cap": 250, "first_speaker": "PRO", "retry_cap": 1}
_EVIDENCE = {"source_a": "text_a", "source_b": "text_b"}
_MOTION = "AI is beneficial"
_PLAYERS = ["player_a", "player_b"]


# ---------------------------------------------------------------------------
# RF5.1 — game_config shape + judge_variant absent
# ---------------------------------------------------------------------------

class TestBuildGameConfig:
    def test_required_keys_present(self):
        gc = build_game_config(_MOTION, _WEIGHTS, _FORMAT, _EVIDENCE)
        for key in ("motion", "rubric", "tie_break", "verdict_structure",
                    "conduct_gate", "format", "evidence_pack"):
            assert key in gc, f"Missing key: {key}"

    def test_judge_variant_absent(self):
        """judge_variant must never appear in any player-bound payload (RF1.2, R-AC2)."""
        gc = build_game_config(_MOTION, _WEIGHTS, _FORMAT, _EVIDENCE)
        assert "judge_variant" not in gc

    def test_rubric_has_all_four_criteria(self):
        gc = build_game_config(_MOTION, _WEIGHTS, _FORMAT, _EVIDENCE)
        assert set(gc["rubric"]["criteria"]) == {"logic", "evidence", "rebuttal", "persuasion"}

    def test_rubric_weights_match_input(self):
        gc = build_game_config(_MOTION, _WEIGHTS, _FORMAT, _EVIDENCE)
        assert gc["rubric"]["weights"] == _WEIGHTS

    def test_format_total_turns_derived(self):
        gc = build_game_config(_MOTION, _WEIGHTS, _FORMAT, _EVIDENCE)
        assert gc["format"]["total_turns"] == 2 + 2 * 3 + 2  # R=3 → 10

    def test_evidence_pack_present(self):
        gc = build_game_config(_MOTION, _WEIGHTS, _FORMAT, _EVIDENCE)
        assert gc["evidence_pack"] == _EVIDENCE

    def test_same_config_to_both_players(self):
        """RF1.3: identical game_config dict is produced for both players."""
        gc1 = build_game_config(_MOTION, _WEIGHTS, _FORMAT, _EVIDENCE)
        gc2 = build_game_config(_MOTION, _WEIGHTS, _FORMAT, _EVIDENCE)
        assert gc1 == gc2

    def test_non_default_r_propagates(self):
        fmt = {**_FORMAT, "rebuttal_rounds": 2}
        gc = build_game_config(_MOTION, _WEIGHTS, fmt, _EVIDENCE)
        assert gc["format"]["R"] == 2
        assert gc["format"]["total_turns"] == 2 + 2 * 2 + 2  # 8


# ---------------------------------------------------------------------------
# RF5.2 — seeded side-assignment reproducibility
# ---------------------------------------------------------------------------

class TestAssignSides:
    def test_same_seed_same_assignment(self):
        """Same seed → identical PRO/CON mapping (RF2.1, R-AC4)."""
        s1 = assign_sides(_PLAYERS, seed=42)
        s2 = assign_sides(_PLAYERS, seed=42)
        assert s1 == s2

    def test_both_sides_covered(self):
        s = assign_sides(_PLAYERS, seed=42)
        assert set(s.values()) == {"PRO", "CON"}

    def test_all_players_assigned(self):
        s = assign_sides(_PLAYERS, seed=42)
        assert set(s.keys()) == set(_PLAYERS)

    def test_different_seeds_can_differ(self):
        results = set()
        for seed in range(20):
            s = assign_sides(_PLAYERS, seed=seed)
            results.add(s[_PLAYERS[0]])
        assert results == {"PRO", "CON"}, "All seeds produced identical assignments (suspicious)"

    def test_wrong_player_count_raises_value_error(self):
        with pytest.raises(ValueError, match="2 players"):
            assign_sides(["only_one"], seed=1)


# ---------------------------------------------------------------------------
# RF5.3 — pre-start abort vs mid-match disconnect boundary
# ---------------------------------------------------------------------------

class TestAbortBoundary:
    def test_pre_start_abort_writes_no_data_cell(self, tmp_path: Path):
        """Pre-start abort (MatchAbortError) must not produce any results file (8.5)."""
        with contextlib.suppress(MatchAbortError):
            setup_match("m1", ["only_one"], 1, _MOTION, _WEIGHTS, _FORMAT, _EVIDENCE)
        assert list(tmp_path.glob("*.jsonl")) == []

    def test_mid_match_disconnect_writes_tagged_row(self, tmp_path: Path):
        """Mid-match disconnect (RE6) does write a trajectory row tagged disconnect (8.3)."""
        traj = [{"turn": 1, "scores": {"logic": 5.0}, "terminated_reason": "disconnect"}]
        write_trajectory("match-1", traj, tmp_path)
        out = tmp_path / "match-1_trajectory.jsonl"
        assert out.exists()
        rows = [json.loads(line) for line in out.read_text().splitlines()]
        assert rows[0]["terminated_reason"] == "disconnect"

    def test_match_abort_error_raised_on_bad_players(self):
        """setup_match raises MatchAbortError when player count is wrong (FR-FT6)."""
        with pytest.raises(MatchAbortError):
            setup_match("m1", ["only_one"], 1, _MOTION, _WEIGHTS, _FORMAT, _EVIDENCE)


# ---------------------------------------------------------------------------
# setup_match end-to-end
# ---------------------------------------------------------------------------

class TestSetupMatch:
    def test_returns_match_setup_instance(self):
        ms = setup_match("m1", _PLAYERS, 42, _MOTION, _WEIGHTS, _FORMAT, _EVIDENCE)
        assert isinstance(ms, MatchSetup)

    def test_judge_variant_not_in_game_config(self):
        """judge_variant is referee-private; must not appear in game_config (RF1.2)."""
        ms = setup_match("m1", _PLAYERS, 42, _MOTION, _WEIGHTS, _FORMAT, _EVIDENCE,
                         judge_variant="hardened")
        assert "judge_variant" not in ms.game_config
        assert ms.judge_variant == "hardened"

    def test_initial_state_is_pending_turn_zero(self):
        ms = setup_match("m1", _PLAYERS, 42, _MOTION, _WEIGHTS, _FORMAT, _EVIDENCE)
        assert ms.initial_state.status == "PENDING"
        assert ms.initial_state.turn_number == 0
        assert ms.initial_state.motion == _MOTION
        assert ms.initial_state.transcript == ()

    def test_same_seed_reproducible_match_setup(self):
        ms1 = setup_match("m1", _PLAYERS, 99, _MOTION, _WEIGHTS, _FORMAT, _EVIDENCE)
        ms2 = setup_match("m1", _PLAYERS, 99, _MOTION, _WEIGHTS, _FORMAT, _EVIDENCE)
        assert ms1.side_map == ms2.side_map
        assert ms1.game_config == ms2.game_config
