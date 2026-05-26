"""Integration tests for player agent wiring and lifecycle (Module P7, RP7.6)."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from agent_arena.services.player.agent import PlayerAgent
from agent_arena.services.protocol.codec import decode, encode
from agent_arena.services.protocol.envelope import Envelope
from agent_arena.services.protocol.message_types import MessageType
from tests.unit.services.player.brain.test_llm_brain import FakeLLMClient


class MockChannel:
    """In-memory channel mimicking TCP framed channel."""

    def __init__(self, recv_messages: list[Envelope]) -> None:
        self.sent: list[Envelope] = []
        self.recv_queue = [encode(msg) for msg in recv_messages]

    def send(self, data: bytes) -> None:
        self.sent.append(decode(data))

    def recv(self) -> bytes:
        if not self.recv_queue:
            return b""
        return self.recv_queue.pop(0)

    def close(self) -> None:
        pass


def test_player_agent_llm_integration_lifecycle(tmp_path: Path) -> None:
    """Verify player agent integrates with LLMPlayerBrain, trace capture, and file output."""
    # 1. Prepare fake config
    results_dir = tmp_path / "results"
    config = {
        "llm": {"model_name": "custom-llm", "generation_seed": 77},
        "debate": {
            "player": {
                "brain_choice": "llm",
                "best_of_N": 2,
                "temperature": 0.5,
                "top_p": 0.9,
                "selector_weights": {"sycophancy": 1.0},
                "private_capture": True,
                "ablation": {
                    "master": True,
                    "vectors": {"sycophancy": True, "bestN_judge_select": True},
                    "baseline_mode": "beta",
                },
            },
            "match": {
                "run_id": "test_run_999",
                "results_dir": str(results_dir),
            },
        },
    }

    # 2. Mock LLM response
    response_data = {
        "read_profile": {"susceptibility": {"sycophancy": 0.9}},
        "reflexion_lesson": "Turn 1 lesson learned",
        "candidate_drafts": [
            {"text": "Draft 1", "targets": []},
            {"text": "Draft 2", "targets": ["sycophancy"]},
        ],
    }
    llm_client = FakeLLMClient(json.dumps(response_data))

    # 3. Queue mock referee messages
    ref_msgs = [
        Envelope("1.00", MessageType.REGISTER_ACK, "match-abc", "referee", 1, "2026-05-26T00:00:00Z", {"match_id": "match-abc"}),
        Envelope(
            "1.00",
            MessageType.ROLE_ASSIGN,
            "match-abc",
            "referee",
            2,
            "2026-05-26T00:00:00Z",
            payload={
                "role": "PRO",
                "game_config": {
                    "rubric": {"weights": {"logic": 100}},
                    "evidence_pack": {"pack_id": "evidence_1"},
                },
            },
        ),
        Envelope(
            "1.00",
            MessageType.MOVE_REQUEST,
            "match-abc",
            "referee",
            3,
            "2026-05-26T00:00:00Z",
            payload={
                "state": {"turn_number": 1, "phase": "OPENING"},
                "legal_moves": [],
            },
        ),
        Envelope("1.00", MessageType.GAME_OVER, "match-abc", "referee", 4, "2026-05-26T00:00:00Z", payload={}),
    ]

    channel = MockChannel(ref_msgs)
    agent = PlayerAgent(
        player_id="player-123",
        channel=channel,  # type: ignore[arg-type]
        seed=123,
        config=config,
    )

    # Inject LLMPlayerBrain using the fake LLMClient
    from agent_arena.services.player.brain.llm_brain import LLMPlayerBrain

    agent.brain = LLMPlayerBrain(client=llm_client, config=config)  # type: ignore[arg-type]

    # 4. Run agent
    agent.run()

    # 5. Assertions on messages sent
    assert len(channel.sent) == 2  # REGISTER and MOVE_SUBMIT
    assert channel.sent[0].type == MessageType.REGISTER
    assert channel.sent[1].type == MessageType.MOVE_SUBMIT
    assert channel.sent[1].payload["move"]["text"] == "Draft 2"

    # 6. Assertions on trace buffer and scratchpad
    assert len(agent.trace_buffer) == 1
    trace = agent.trace_buffer[0]
    assert trace["match_id"] == "match-abc"
    assert trace["turn_number"] == 1
    assert trace["reflexion_lesson"] == "Turn 1 lesson learned"

    # Check scratchpad: both lesson and profile were appended
    assert "Turn 1 lesson learned" in agent.scratchpad
    assert response_data["read_profile"] in agent.scratchpad

    # 7. Assertions on dump file
    dump_file = results_dir / "test_run_999" / "match-abc.player_PRO.jsonl"
    assert dump_file.exists()

    with dump_file.open("r", encoding="utf-8") as f:
        lines = f.readlines()
        assert len(lines) == 1
        written_trace = json.loads(lines[0])
        assert written_trace["reflexion_lesson"] == "Turn 1 lesson learned"

    # Clean up results
    shutil.rmtree(results_dir, ignore_errors=True)
