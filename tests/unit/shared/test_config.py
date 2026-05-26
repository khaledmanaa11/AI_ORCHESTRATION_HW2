import json
from pathlib import Path

import pytest

from agent_arena.shared.config import load_logging_config, load_setup_config


def test_load_setup_config_success(tmp_path: Path) -> None:
    config_data = {
        "version": "1.00",
        "network": {
            "host": "127.0.0.1",
            "port": 9000,
            "player_count": 2,
            "connect_timeout_seconds": 5.0,
            "read_timeout_seconds": 15.0
        },
        "game": {
            "move_timeout_seconds": 10.0
        },
        "framing": {
            "max_frame_size_bytes": 10485760
        },
        "llm": {
            "model_name": "claude-opus-4-5"
        },
        "debate": {
            "format": {
                "rebuttal_rounds": 3,
                "word_cap": 250,
                "first_speaker": "PRO",
                "retry_cap": 1
            },
            "judge": {
                "variant": "naive",
                "weights": { "logic": 30, "evidence": 30, "rebuttal": 25, "persuasion": 15 }
            },
            "player": {
                "best_of_N": 3,
                "private_capture": True,
                "ablation": {
                    "master": False,
                    "vectors": {},
                    "baseline_mode": "beta"
                }
            },
            "match": { "motion": "AI is beneficial", "evidence_pack": "pack_001", "seed": 42 }
        }
    }
    config_file = tmp_path / "setup.json"
    with config_file.open("w", encoding="utf-8") as f:
        json.dump(config_data, f)

    config = load_setup_config(config_file)
    assert config.version == "1.00"
    assert config.network.host == "127.0.0.1"
    assert config.network.port == 9000
    assert config.game.move_timeout_seconds == 10.0
    assert config.framing.max_frame_size_bytes == 10485760
    assert config.llm.model_name == "claude-opus-4-5"
    assert config.debate.format.rebuttal_rounds == 3

def test_load_setup_config_version_mismatch(tmp_path: Path) -> None:
    config_data = {
        "version": "0.99",
        "network": {
            "host": "127.0.0.1",
            "port": 9000,
            "player_count": 2,
            "connect_timeout_seconds": 5.0,
            "read_timeout_seconds": 15.0
        },
        "game": {
            "move_timeout_seconds": 10.0
        },
        "framing": {
            "max_frame_size_bytes": 10485760
        },
        "llm": {
            "model_name": "claude-opus-4-5"
        },
        "debate": {
            "format": {
                "rebuttal_rounds": 3,
                "word_cap": 250,
                "first_speaker": "PRO",
                "retry_cap": 1
            },
            "judge": {
                "variant": "naive",
                "weights": { "logic": 30, "evidence": 30, "rebuttal": 25, "persuasion": 15 }
            },
            "player": {
                "best_of_N": 3,
                "private_capture": True,
                "ablation": {
                    "master": False,
                    "vectors": {},
                    "baseline_mode": "beta"
                }
            },
            "match": { "motion": "AI is beneficial", "evidence_pack": "pack_001", "seed": 42 }
        }
    }
    config_file = tmp_path / "setup.json"
    with config_file.open("w", encoding="utf-8") as f:
        json.dump(config_data, f)

    with pytest.raises(ValueError, match="Config version mismatch"):
        load_setup_config(config_file)

def test_load_logging_config_success(tmp_path: Path) -> None:
    config_data = {
        "version": "1.00",
        "logging": {
            "version": 1,
            "root": {
                "level": "INFO",
                "handlers": ["console"]
            }
        }
    }
    config_file = tmp_path / "logging_config.json"
    with config_file.open("w", encoding="utf-8") as f:
        json.dump(config_data, f)

    logging_config = load_logging_config(config_file)
    assert logging_config["version"] == 1
    assert "root" in logging_config

def test_load_logging_config_version_mismatch(tmp_path: Path) -> None:
    config_data = {
        "version": "0.99",
        "logging": {}
    }
    config_file = tmp_path / "logging_config.json"
    with config_file.open("w", encoding="utf-8") as f:
        json.dump(config_data, f)

    with pytest.raises(ValueError, match="Logging config version mismatch"):
        load_logging_config(config_file)
