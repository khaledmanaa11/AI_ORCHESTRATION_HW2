import subprocess
import types

import pytest

from agent_arena.shared import api_gatekeeper
from agent_arena.shared.api_gatekeeper import APIGatekeeper, get_default_gatekeeper
from agent_arena.shared.llm_client import GeminiCLIClient, GoogleGenAIClient


def test_direct_clients_share_default_gatekeeper(monkeypatch):
    class FakeGatekeeperConfig:
        def __init__(self):
            self.rpm = 100
            self.rpd = 1000
            self.max_concurrency = 8
            self.breaker_threshold = 5
            self.breaker_window_seconds = 60.0
            self.breaker_cooldown_seconds = 30.0
            self.acquire_timeout_seconds = 1.0

        def model_dump(self):
            return {
                "rpm": self.rpm,
                "rpd": self.rpd,
                "max_concurrency": self.max_concurrency,
                "breaker_threshold": self.breaker_threshold,
                "breaker_window_seconds": self.breaker_window_seconds,
                "breaker_cooldown_seconds": self.breaker_cooldown_seconds,
                "acquire_timeout_seconds": self.acquire_timeout_seconds,
            }

    class FakeSetupConfig:
        def __init__(self):
            self.llm = types.SimpleNamespace(gatekeeper=FakeGatekeeperConfig())

    fake_gatekeeper_cfg = FakeSetupConfig()

    monkeypatch.setattr(api_gatekeeper, "_DEFAULT_GATEKEEPER", None)
    monkeypatch.setattr(
        api_gatekeeper,
        "load_setup_config",
        lambda path: fake_gatekeeper_cfg,
    )
    monkeypatch.setenv("GOOGLE_API_KEY", "fake-key")
    monkeypatch.setattr("agent_arena.shared.llm_client.load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        "agent_arena.shared.llm_client.genai.Client",
        lambda api_key: types.SimpleNamespace(models=types.SimpleNamespace(generate_content=lambda *args, **kwargs: None)),
    )
    monkeypatch.setattr(
        "agent_arena.shared.llm_client.shutil.which",
        lambda binary: "/usr/bin/gemini",
    )

    google_client = GoogleGenAIClient()
    gemini_client = GeminiCLIClient()

    assert google_client._gatekeeper is gemini_client._gatekeeper
    assert google_client._gatekeeper is get_default_gatekeeper()


def test_gemini_retry_backoff_releases_gatekeeper_slot(monkeypatch):
    gatekeeper = APIGatekeeper(
        rpm=10,
        rpd=10,
        max_concurrency=1,
        breaker_threshold=3,
        breaker_window_seconds=10.0,
        breaker_cooldown_seconds=30.0,
        acquire_timeout_seconds=1.0,
    )

    monkeypatch.setattr("agent_arena.shared.llm_client.load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.setenv("GEMINI_CLI_BIN", "gemini")
    monkeypatch.setattr(
        "agent_arena.shared.llm_client.shutil.which",
        lambda binary: "/usr/bin/gemini",
    )

    client = GeminiCLIClient(gatekeeper=gatekeeper)

    sleep_called = []

    def fake_sleep(seconds):
        snapshot = gatekeeper.snapshot()
        assert snapshot["in_flight"] == 0
        sleep_called.append(seconds)

    monkeypatch.setattr("agent_arena.shared.llm_client.time.sleep", fake_sleep)

    first_result = subprocess.CompletedProcess(
        args=["gemini", "-m", "model", "-p", "prompt"],
        returncode=1,
        stdout="",
        stderr="429 rate limit",
    )
    second_result = subprocess.CompletedProcess(
        args=["gemini", "-m", "model", "-p", "prompt"],
        returncode=0,
        stdout="ok",
        stderr="",
    )

    def fake_run(*args, **kwargs):
        return first_result if not sleep_called else second_result

    monkeypatch.setattr("agent_arena.shared.llm_client.subprocess.run", fake_run)

    response = client._run("prompt", "model")

    assert response == "ok"
    assert len(sleep_called) == 1
