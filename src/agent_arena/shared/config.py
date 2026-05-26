import json
from pathlib import Path

from pydantic import BaseModel, Field, model_validator

from agent_arena.constants import EXPECTED_CONFIG_VERSION


class NetworkConfig(BaseModel):
    host: str = Field(..., description="TCP server host IP")
    port: int = Field(..., description="TCP server port")
    player_count: int = Field(2, description="Number of players required")
    connect_timeout_seconds: float = Field(5.0, description="Connection timeout")
    read_timeout_seconds: float = Field(15.0, description="Socket read timeout")

class GameConfig(BaseModel):
    move_timeout_seconds: float = Field(10.0, description="Per-move timeout limit")
    lobby_timeout_seconds: float = Field(
        30.0, description="Max wait for all players to register before lobby is closed"
    )
    heartbeat_interval_seconds: float = Field(
        5.0, description="Interval between keep-alive heartbeat messages"
    )

class FramingConfig(BaseModel):
    max_frame_size_bytes: int = Field(10485760, description="Max frame buffer size in bytes")

class LLMConfig(BaseModel):
    provider: str = Field("google", description="LLM provider name")
    model_name: str = Field(..., description="LLM model identifier used by brains")

# ── Debate config submodels (Module G) ──────────────────────────────

class DebateFormatConfig(BaseModel):
    rebuttal_rounds: int = 3
    word_cap: int = 250
    first_speaker: str = "PRO"
    retry_cap: int = 1

class DebateJudgeConfig(BaseModel):
    variant: str = "naive"
    weights: dict[str, int] = {"logic": 30, "evidence": 30, "rebuttal": 25, "persuasion": 15}

    @model_validator(mode="after")
    def weights_sum_100(self) -> "DebateJudgeConfig":
        if sum(self.weights.values()) != 100:
            raise ValueError("judge weights must sum to 100")
        if self.variant not in {"naive", "hardened", "structural"}:
            raise ValueError(f"unknown judge variant: {self.variant}")
        return self

class DebateAblationConfig(BaseModel):
    master: bool = False
    vectors: dict[str, bool] = {}
    baseline_mode: str = "beta"

class DebatePlayerConfig(BaseModel):
    best_of_N: int = 3  # noqa: N815
    private_capture: bool = True
    ablation: DebateAblationConfig = DebateAblationConfig()

class DebateMatchConfig(BaseModel):
    motion: str
    evidence_pack: str
    seed: int

class DebateConfig(BaseModel):
    format: DebateFormatConfig = DebateFormatConfig()
    judge: DebateJudgeConfig = DebateJudgeConfig()
    player: DebatePlayerConfig = DebatePlayerConfig()
    match: DebateMatchConfig

# ── Root config ─────────────────────────────────────────────────────

class SetupConfig(BaseModel):
    version: str = Field(..., description="Configuration file schema version")
    network: NetworkConfig
    game: GameConfig
    framing: FramingConfig
    llm: LLMConfig
    debate: DebateConfig

def load_setup_config(path: str | Path) -> SetupConfig:
    with Path(path).open(encoding="utf-8") as f:
        data = json.load(f)

    config = SetupConfig(**data)
    if config.version != EXPECTED_CONFIG_VERSION:
        raise ValueError(
            f"Config version mismatch: expected {EXPECTED_CONFIG_VERSION}, got {config.version}"
        )
    return config

def load_logging_config(path: str | Path) -> dict:
    with Path(path).open(encoding="utf-8") as f:
        data = json.load(f)

    version = data.get("version")
    if version != EXPECTED_CONFIG_VERSION:
        raise ValueError(
            f"Logging config version mismatch: expected {EXPECTED_CONFIG_VERSION}, got {version}"
        )
    return data.get("logging", {})
