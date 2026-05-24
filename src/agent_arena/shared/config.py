import json
from pathlib import Path

from pydantic import BaseModel, Field

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
    model_name: str = Field(..., description="Anthropic model identifier used by LLM brains")

class SetupConfig(BaseModel):
    version: str = Field(..., description="Configuration file schema version")
    network: NetworkConfig
    game: GameConfig
    framing: FramingConfig
    llm: LLMConfig

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
