import json
from pathlib import Path

from agent_arena.shared.logging_setup import setup_logging


def test_setup_logging_file_not_found() -> None:
    # Shoud run without crashing, falling back to basicConfig
    setup_logging("non_existent_file.json")

def test_setup_logging_success(tmp_path: Path) -> None:
    log_file_path = tmp_path / "logs" / "arena.log"
    config_data = {
        "version": "1.00",
        "logging": {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "standard": {
                    "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
                }
            },
            "handlers": {
                "file": {
                    "class": "logging.FileHandler",
                    "filename": str(log_file_path),
                    "formatter": "standard"
                }
            },
            "root": {
                "level": "INFO",
                "handlers": ["file"]
            }
        }
    }
    config_file = tmp_path / "logging_config.json"
    with config_file.open("w", encoding="utf-8") as f:
        json.dump(config_data, f)

    # Shoud create the log_file_path's parent directory and initialize
    setup_logging(config_file)
    assert log_file_path.parent.exists()

def test_setup_logging_version_mismatch(tmp_path: Path) -> None:
    config_data = {
        "version": "0.99",
        "logging": {}
    }
    config_file = tmp_path / "logging_config.json"
    with config_file.open("w", encoding="utf-8") as f:
        json.dump(config_data, f)

    setup_logging(config_file)

def test_setup_logging_invalid_config(tmp_path: Path) -> None:
    config_data = {
        "version": "1.00",
        "logging": {
            "version": 1,
            "handlers": {
                "file": {
                    "class": "logging.NonExistentClass",
                    "filename": "somefile.log"
                }
            }
        }
    }
    config_file = tmp_path / "logging_config.json"
    with config_file.open("w", encoding="utf-8") as f:
        json.dump(config_data, f)

    setup_logging(config_file)
