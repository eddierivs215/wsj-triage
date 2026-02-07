"""Tests for synthesis JSON extraction and helpers."""
import json
import pytest
from src.synthesis import (
    extract_first_json_object,
    coerce_to_object,
    escape_html,
    parse_dt,
)


# ── extract_first_json_object ──────────────────────────────

class TestExtractFirstJsonObject:
    def test_clean_json_line(self):
        obj = {"title": "Test", "score": 42}
        result = extract_first_json_object(json.dumps(obj))
        assert json.loads(result) == obj

    def test_json_with_leading_text(self):
        line = 'some prefix text {"key": "value"}'
        result = extract_first_json_object(line)
        assert json.loads(result) == {"key": "value"}

    def test_json_with_trailing_text(self):
        line = '{"key": "value"} trailing text'
        result = extract_first_json_object(line)
        assert json.loads(result) == {"key": "value"}

    def test_nested_braces(self):
        obj = {"outer": {"inner": 1}}
        result = extract_first_json_object(json.dumps(obj))
        assert json.loads(result) == obj

    def test_braces_in_strings(self):
        obj = {"text": "a {b} c"}
        result = extract_first_json_object(json.dumps(obj))
        assert json.loads(result) == obj

    def test_empty_input(self):
        assert extract_first_json_object("") is None
        assert extract_first_json_object(None) is None

    def test_no_json(self):
        assert extract_first_json_object("just plain text") is None


# ── coerce_to_object ──────────────────────────────────────

class TestCoerceToObject:
    def test_dict_passthrough(self):
        d = {"a": 1}
        assert coerce_to_object(d) == d

    def test_json_string(self):
        assert coerce_to_object('{"a": 1}') == {"a": 1}

    def test_non_object(self):
        assert coerce_to_object([1, 2]) is None
        assert coerce_to_object(42) is None


# ── escape_html ────────────────────────────────────────────

class TestEscapeHtml:
    def test_escapes_angle_brackets(self):
        assert "&lt;" in escape_html("<script>")
        assert "&gt;" in escape_html("a > b")

    def test_escapes_ampersand(self):
        assert "&amp;" in escape_html("a & b")

    def test_escapes_quotes(self):
        result = escape_html('say "hello"')
        assert "&quot;" in result or "&#x27;" in result or '"' not in result.replace("&quot;", "")

    def test_empty_string(self):
        assert escape_html("") == ""
        assert escape_html(None) == ""


# ── parse_dt ───────────────────────────────────────────────

class TestParseDt:
    def test_iso_format(self):
        dt = parse_dt("2025-01-30T12:00:00+00:00")
        assert dt is not None
        assert dt.year == 2025

    def test_z_suffix(self):
        dt = parse_dt("2025-01-30T12:00:00Z")
        assert dt is not None

    def test_empty(self):
        assert parse_dt("") is None
        assert parse_dt(None) is None

    def test_invalid(self):
        assert parse_dt("not-a-date") is None
