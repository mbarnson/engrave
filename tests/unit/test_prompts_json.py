"""Tests for JSON generation prompt suffix and extraction utilities.

Covers build_json_generation_suffix and extract_json_from_response
from engrave.generation.prompts.
"""

from __future__ import annotations

import json

from engrave.generation.prompts import (
    build_json_generation_suffix,
    extract_json_from_response,
)


class TestBuildJsonGenerationSuffix:
    """Tests for build_json_generation_suffix."""

    def test_returns_string(self):
        result = build_json_generation_suffix(["Trumpet 1", "Trombone"])
        assert isinstance(result, str)
        assert len(result) > 0

    def test_contains_all_instrument_names(self):
        instruments = ["Trumpet 1", "Alto Saxophone", "Piano"]
        result = build_json_generation_suffix(instruments)
        for name in instruments:
            assert name in result

    def test_contains_json_example(self):
        result = build_json_generation_suffix(["Trumpet"])
        assert '"pitch"' in result
        assert '"duration"' in result
        assert '"measures"' in result
        assert '"notes"' in result

    def test_contains_format_rules(self):
        result = build_json_generation_suffix(["Trumpet"])
        assert "rest" in result
        assert "dynamic" in result.lower()
        assert "quarterLength" in result

    def test_single_instrument(self):
        result = build_json_generation_suffix(["Bass"])
        assert '"Bass"' in result

    def test_empty_instrument_list(self):
        result = build_json_generation_suffix([])
        assert isinstance(result, str)
        assert len(result) > 0


class TestExtractJsonFromResponse:
    """Tests for extract_json_from_response."""

    def test_clean_json_array(self):
        data = [
            {"instrument": "trumpet", "measures": [{"number": 1, "notes": []}]},
            {"instrument": "trombone", "measures": [{"number": 1, "notes": []}]},
        ]
        response = json.dumps(data)
        result = extract_json_from_response(response)
        assert len(result) == 2
        assert result[0]["instrument"] == "trumpet"
        assert result[1]["instrument"] == "trombone"

    def test_markdown_code_block_wrapping(self):
        data = [{"instrument": "trumpet", "measures": []}]
        response = f"```json\n{json.dumps(data, indent=2)}\n```"
        result = extract_json_from_response(response)
        assert len(result) == 1
        assert result[0]["instrument"] == "trumpet"

    def test_generic_code_block_wrapping(self):
        data = [{"instrument": "piano", "measures": []}]
        response = f"```\n{json.dumps(data)}\n```"
        result = extract_json_from_response(response)
        assert len(result) == 1
        assert result[0]["instrument"] == "piano"

    def test_surrounding_commentary(self):
        data = [{"instrument": "bass", "key": "c_major", "measures": []}]
        response = (
            "Here is the JSON notation for the bass part:\n\n"
            f"```json\n{json.dumps(data, indent=2)}\n```\n\n"
            "I hope this helps with the generation."
        )
        result = extract_json_from_response(response)
        assert len(result) == 1
        assert result[0]["instrument"] == "bass"

    def test_malformed_json_returns_empty_list(self):
        response = "This is not JSON at all { broken : stuff"
        result = extract_json_from_response(response)
        assert result == []

    def test_single_json_object_wraps_in_list(self):
        data = {"instrument": "flute", "measures": [{"number": 1, "notes": []}]}
        response = json.dumps(data)
        result = extract_json_from_response(response)
        assert len(result) == 1
        assert result[0]["instrument"] == "flute"

    def test_individual_json_objects_in_text(self):
        """When the LLM outputs multiple JSON objects without wrapping them in an array."""
        obj1 = json.dumps({"instrument": "trumpet", "measures": []})
        obj2 = json.dumps({"instrument": "trombone", "measures": []})
        response = f"Trumpet:\n{obj1}\n\nTrombone:\n{obj2}"
        result = extract_json_from_response(response)
        assert len(result) == 2
        instruments = {r["instrument"] for r in result}
        assert instruments == {"trumpet", "trombone"}

    def test_empty_string_returns_empty_list(self):
        result = extract_json_from_response("")
        assert result == []

    def test_nested_json_in_measures(self):
        """Realistic LLM output with nested measure/note structure."""
        data = [
            {
                "instrument": "alto_sax",
                "key": "bf_major",
                "time_signature": "4/4",
                "measures": [
                    {
                        "number": 1,
                        "notes": [
                            {"pitch": "bf4", "beat": 1.0, "duration": 1.0, "dynamic": "mf"},
                            {"pitch": "d5", "beat": 2.0, "duration": 0.5},
                            {"type": "rest", "beat": 3.0, "duration": 2.0},
                        ],
                    }
                ],
            }
        ]
        response = json.dumps(data)
        result = extract_json_from_response(response)
        assert len(result) == 1
        assert result[0]["measures"][0]["notes"][0]["pitch"] == "bf4"
        assert result[0]["measures"][0]["notes"][2]["type"] == "rest"
