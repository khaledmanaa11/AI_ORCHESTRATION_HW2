"""Unit tests to verify no player brain module directly imports the Gemini SDK (PL-AC3)."""
from __future__ import annotations

import ast
from pathlib import Path

import agent_arena.services.player.brain


def test_no_direct_sdk_imports() -> None:
    """Verify that player brain modules never import the Google GenAI/GenerativeAI SDKs directly."""
    brain_dir = Path(agent_arena.services.player.brain.__file__).parent
    py_files = list(brain_dir.glob("*.py"))

    assert len(py_files) > 0, "No Python modules found in the player brain package."

    # Forbidden import namespaces / names
    forbidden_prefixes = ("google.generativeai", "google.genai", "google")

    for py_file in py_files:
        if py_file.name == "__init__.py":
            continue

        with py_file.open(encoding="utf-8") as f:
            source = f.read()

        tree = ast.parse(source, filename=str(py_file))

        # Check imports using AST traversal
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    # Check if importing google, google.genai, google.generativeai, etc.
                    for prefix in forbidden_prefixes:
                        if alias.name == prefix or alias.name.startswith(prefix + "."):
                            raise AssertionError(
                                f"Module {py_file.name} directly imports forbidden SDK module {alias.name}"
                            )
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    for prefix in forbidden_prefixes:
                        if node.module == prefix or node.module.startswith(prefix + "."):
                            raise AssertionError(
                                f"Module {py_file.name} directly imports from forbidden SDK module {node.module}"
                            )

            # Ensure they don't use raw SDK naming conventions or references to google.generativeai / google.genai
            # (e.g. as attribute lookup on an un-imported or dynamically imported module, or within expressions)
            elif isinstance(node, ast.Name):
                for prefix in forbidden_prefixes[:2]:  # google.generativeai, google.genai
                    assert prefix not in node.id, (
                        f"Module {py_file.name} references forbidden SDK name {node.id}"
                    )
            elif isinstance(node, ast.Attribute):
                for prefix in forbidden_prefixes[:2]:  # google.generativeai, google.genai
                    assert prefix not in node.attr, (
                        f"Module {py_file.name} references forbidden SDK attribute {node.attr}"
                    )
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                for prefix in forbidden_prefixes[:2]:  # google.generativeai, google.genai
                    # Allow reference to google-genai or similar in docstrings or comments, but reject
                    # exact matches or imports in string form
                    if node.value == prefix or node.value.startswith(prefix + "."):
                        raise AssertionError(
                            f"Module {py_file.name} references forbidden SDK string {node.value}"
                        )


def test_llm_brain_only_obtains_llm_access_via_llm_client() -> None:
    """Verify that if a player brain module interacts with LLMs, it uses LLMClient."""
    brain_dir = Path(agent_arena.services.player.brain.__file__).parent
    py_files = list(brain_dir.glob("*.py"))

    # We expect llm_brain.py to interact with LLMs, and it must import LLMClient.
    # Other files do not interact with LLMs.
    for py_file in py_files:
        if py_file.name == "__init__.py":
            continue

        with py_file.open(encoding="utf-8") as f:
            source = f.read()

        tree = ast.parse(source, filename=str(py_file))

        imports_llm_client = False
        imports_any_other_client = False

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module == "agent_arena.shared.llm_client":
                    for alias in node.names:
                        if alias.name == "LLMClient":
                            imports_llm_client = True
                # Check if anyone imports other client libraries directly
                if node.module and ("client" in node.module.lower() or "sdk" in node.module.lower()) and node.module != "agent_arena.shared.llm_client":
                    imports_any_other_client = True
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if "client" in alias.name.lower() or "sdk" in alias.name.lower():
                        imports_any_other_client = True

        if py_file.name == "llm_brain.py":
            assert imports_llm_client, "llm_brain.py must import LLMClient to obtain LLM access."
            assert not imports_any_other_client, "llm_brain.py must not import any other LLM clients/SDKs."
        else:
            assert not imports_llm_client, f"{py_file.name} does not need LLM access and should not import LLMClient."
