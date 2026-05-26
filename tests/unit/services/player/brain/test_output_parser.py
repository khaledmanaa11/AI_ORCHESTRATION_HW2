"""Unit tests for Module P3 (Output Parser) in output_parser.py (RP3.1-RP3.3)."""
from __future__ import annotations

from agent_arena.services.player.brain.output_parser import ParsedTurn, parse


def test_parse_well_formed_json() -> None:
    """Ensure well-formed JSON parses into the typed ParsedTurn structure (RP3.1)."""
    raw = """
    {
        "read_profile": {
            "revealed_criterion_emphasis": "logical flow",
            "style_notes": "academic tone",
            "susceptibility": {"sycophancy": 0.8}
        },
        "reflexion_lesson": "Be more concise next time",
        "candidate_drafts": [
            {"text": "Draft 1", "targets": ["sycophancy"]},
            {"text": "Draft 2", "targets": []}
        ]
    }
    """
    result = parse(raw)
    assert isinstance(result, ParsedTurn)
    assert result.read_profile == {
        "revealed_criterion_emphasis": "logical flow",
        "style_notes": "academic tone",
        "susceptibility": {"sycophancy": 0.8},
    }
    assert result.reflexion_lesson == "Be more concise next time"
    assert len(result.candidate_drafts) == 2
    assert result.candidate_drafts[0] == {"text": "Draft 1", "targets": ["sycophancy"]}
    assert result.candidate_drafts[1] == {"text": "Draft 2", "targets": []}


def test_parse_well_formed_with_markdown_fences() -> None:
    """Ensure JSON inside markdown code blocks is extracted and parsed."""
    raw = "```json\n{\n\"read_profile\": {},\n\"reflexion_lesson\": \"None\",\n\"candidate_drafts\": [\n{\"text\": \"Hello world\", \"targets\": []}\n]\n}\n```"
    result = parse(raw)
    assert isinstance(result, ParsedTurn)
    assert result.candidate_drafts == [{"text": "Hello world", "targets": []}]


def test_parse_malformed_json_fallback() -> None:
    """Ensure malformed JSON falls back to a safe draft and empty lesson/profile (RP3.2)."""
    raw = "This is not json { some incomplete: json"
    result = parse(raw)
    assert isinstance(result, ParsedTurn)
    assert result.read_profile == {}
    assert result.reflexion_lesson == ""
    assert result.candidate_drafts == [{"text": raw, "targets": []}]


def test_parse_empty_string_fallback() -> None:
    """Ensure empty input falls back to a safe draft."""
    result = parse("")
    assert isinstance(result, ParsedTurn)
    assert result.read_profile == {}
    assert result.reflexion_lesson == ""
    assert result.candidate_drafts == [{"text": "", "targets": []}]


def test_parse_missing_fields_fallback() -> None:
    """Ensure missing key fields fall back appropriately (RP3.2)."""
    # missing candidate_drafts should trigger fallback
    raw = """
    {
        "read_profile": {"a": 1},
        "reflexion_lesson": "Lesson learned"
    }
    """
    result = parse(raw)
    assert result.read_profile == {}
    assert result.reflexion_lesson == ""
    assert result.candidate_drafts == [{"text": raw, "targets": []}]


def test_parse_draft_normalization() -> None:
    """Ensure drafts missing targets default targets to [] (RP3.3)."""
    raw = """
    {
        "read_profile": {},
        "reflexion_lesson": "",
        "candidate_drafts": [
            {"text": "Draft with missing targets"},
            {"text": "Draft with null targets", "targets": null},
            {"text": "Draft with non-list targets", "targets": "sycophancy"},
            "Draft that is just a string"
        ]
    }
    """
    result = parse(raw)
    assert len(result.candidate_drafts) == 4
    assert result.candidate_drafts[0] == {
        "text": "Draft with missing targets",
        "targets": [],
    }
    assert result.candidate_drafts[1] == {
        "text": "Draft with null targets",
        "targets": [],
    }
    assert result.candidate_drafts[2] == {
        "text": "Draft with non-list targets",
        "targets": [],
    }
    assert result.candidate_drafts[3] == {
        "text": "Draft that is just a string",
        "targets": [],
    }


def test_parse_non_dictionary_json_fallback() -> None:
    """Ensure JSON that is not a dictionary (e.g. list, string) falls back cleanly (RP3.2)."""
    raw = '[1, 2, "three"]'
    result = parse(raw)
    assert result.read_profile == {}
    assert result.reflexion_lesson == ""
    assert result.candidate_drafts == [{"text": raw, "targets": []}]


def test_parse_invalid_types_and_empty_drafts() -> None:
    """Test various invalid fields inside parsed JSON (RP3.2)."""
    # read_profile is not a dict, reflexion_lesson is not a str, draft text is not a str, empty candidate_drafts list
    raw1 = """
    {
        "read_profile": "not_a_dict",
        "reflexion_lesson": 12345,
        "candidate_drafts": [
            {"text": 999, "targets": []},
            {"text": null, "targets": []}
        ]
    }
    """
    result1 = parse(raw1)
    assert result1.read_profile == {}
    assert result1.reflexion_lesson == ""
    assert result1.candidate_drafts == [
        {"text": "999", "targets": []},
        {"text": "", "targets": []}
    ]

    raw2 = """
    {
        "read_profile": {},
        "reflexion_lesson": "",
        "candidate_drafts": []
    }
    """
    result2 = parse(raw2)
    assert result2.candidate_drafts == [{"text": raw2, "targets": []}]


def test_parse_general_exception_fallback() -> None:
    """Ensure that passing a non-string object that causes AttributeError / Exception falls back cleanly."""
    result = parse([1, 2])  # type: ignore[arg-type]
    assert result.read_profile == {}
    assert result.reflexion_lesson == ""
    assert result.candidate_drafts == [{"text": [1, 2], "targets": []}]  # type: ignore[list-item]


def test_parse_braces_fallback_success() -> None:
    """Test when the raw string has extra text before/after valid JSON within braces."""
    raw = 'Some leading text {"read_profile": {}, "reflexion_lesson": "A", "candidate_drafts": [{"text": "B"}]} trailing text'
    result = parse(raw)
    assert result.read_profile == {}
    assert result.reflexion_lesson == "A"
    assert result.candidate_drafts == [{"text": "B", "targets": []}]


