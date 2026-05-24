import logging
import logging.config
from pathlib import Path

from agent_arena.shared.config import load_logging_config


def setup_logging(config_path: str | Path = "config/logging_config.json") -> None:
    """Loads logging configuration from JSON file and initializes logging."""
    config_file = Path(config_path)
    if not config_file.exists():
        logging.basicConfig(level=logging.INFO)
        logging.warning(f"Logging configuration file not found at {config_path}. Using basic configuration.")
        return

    # Load configuration
    try:
        log_config = load_logging_config(config_file)
    except Exception as e:
        logging.basicConfig(level=logging.INFO)
        logging.error(f"Error loading logging config from {config_path}: {e}. Using basic configuration.")
        return

    # Ensure results directory exists for file logging
    handlers = log_config.get("handlers", {})
    for handler_settings in handlers.values():
        if "filename" in handler_settings:
            log_file = Path(handler_settings["filename"])
            log_file.parent.mkdir(parents=True, exist_ok=True)

    try:
        logging.config.dictConfig(log_config)
    except Exception as e:
        logging.basicConfig(level=logging.INFO)
        logging.error(f"Failed to configure logging via dictConfig: {e}. Using basic configuration.")
