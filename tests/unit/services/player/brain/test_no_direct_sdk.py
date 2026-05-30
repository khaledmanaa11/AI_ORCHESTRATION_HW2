"""Tests guarding against direct Gemini SDK imports in player brain modules."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

_BRAIN_DIR = Path(__file__).resolve().parents[5] / "src" / "agent_arena" / "services" / "player" / "brain"


def test_no_direct_sdk_imports() -> None:
    """Assert no player brain modules import google.generativeai or google.genai directly."""
    assert _BRAIN_DIR.is_dir(), f"Brain directory not found at {_BRAIN_DIR}"

    # Get all .py files in the player brain directory
    py_files = list(_BRAIN_DIR.glob("*.py"))
    assert len(py_files) > 0, "No Python files found in player brain directory"

    forbidden = {"google.generativeai", "google.genai", "google"}

    for py_file in py_files:
        source = py_file.read_text(encoding="utf-8")
        tree = ast.parse(source)

        for node in ast.walk(tree):
            # Check standard import: import X, import Y as Z
            if isinstance(node, ast.Import):
                for alias in node.names:
                    # check both exact matches and prefix matches (e.g. google.genai)
                    for f in forbidden:
                        if alias.name == f or alias.name.startswith(f + "."):
                            pytest.fail(
                                f"Module {py_file.name} imports forbidden SDK '{alias.name}' directly."
                            )
            # Check import from: from X import Y
            elif isinstance(node, ast.ImportFrom) and node.module:
                for f in forbidden:
                    if node.module == f or node.module.startswith(f + "."):
                        pytest.fail(
                            f"Module {py_file.name} imports from forbidden SDK '{node.module}' directly."
                        )
