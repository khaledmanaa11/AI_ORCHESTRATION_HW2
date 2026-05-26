"""Integration test for LLM brain swap (Module I - RI3.2)."""
import threading
import time

from pydantic import BaseModel

from agent_arena.services.player.client import PlayerClient
from agent_arena.services.referee.brain.llm_brain import (
    HolisticRationaleResult,
    HolisticTiebreakResult,
    LLMRefereeBrain,
    TurnEvaluationResult,
)
from agent_arena.services.referee.server import RefereeServer
from agent_arena.shared.config import load_setup_config


class OfflineMockLLMRefereeBrain(LLMRefereeBrain):
    """Mock subclass to avoid real network calls during integration test."""
    def __init__(self):
        self._model_name = "mock-model"
        self._client = None

    def _generate_json(self, _prompt: str, schema: type[BaseModel]) -> BaseModel:
        if schema == TurnEvaluationResult:
            return TurnEvaluationResult( # type: ignore
                tell="Mock tell",
                logic_score=8.0,
                evidence_score=9.0,
                rebuttal_score=7.0,
                persuasion_score=8.5,
            )
        if schema == HolisticTiebreakResult:
            return HolisticTiebreakResult(winner="PRO", rationale="Mock tiebreak") # type: ignore
        if schema == HolisticRationaleResult:
            return HolisticRationaleResult(rationale="Mock rationale") # type: ignore
        raise ValueError(f"Unexpected schema {schema}")


def test_integration_llm_swap_lifecycle() -> None:
    """RI3.2: run integration test with LLMRefereeBrain swapped in."""
    config = load_setup_config("config/setup.json")
    config.network.port = 0
    config.network.connect_timeout_seconds = 1.0
    config.network.read_timeout_seconds = 2.0
    config.game.move_timeout_seconds = 2.0

    brain = OfflineMockLLMRefereeBrain()
    ref_server = RefereeServer(config, brain=brain)
    ref_server.start()
    time.sleep(0.1)
    bound_port = ref_server.server.port

    def run_player(pid: str, seed: int) -> None:
        client = PlayerClient(
            player_id=pid,
            host=config.network.host,
            port=bound_port,
            connect_timeout=1.0,
            seed=seed,
            max_retries=3,
            backoff_base=0.05,
        )
        client.start()

    t1 = threading.Thread(target=run_player, args=("player_1", 42), daemon=True)
    t2 = threading.Thread(target=run_player, args=("player_2", 42), daemon=True)
    t1.start()
    t2.start()

    t1.join(timeout=10.0)
    t2.join(timeout=10.0)
    if ref_server.game_thread:
        ref_server.game_thread.join(timeout=10.0)

    ref_server.stop()

    assert ref_server.exception is None
    assert ref_server.final_state is not None
    assert ref_server.final_state.status == "COMPLETE"
    assert ref_server.final_state.verdict is not None
    assert "winner" in ref_server.final_state.verdict
    # Verify the LLM rationale was injected
    assert ref_server.final_state.verdict["rationale"] == "Mock rationale"
