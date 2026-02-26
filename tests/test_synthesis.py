"""Tests for synthesis helpers and JSONL loading."""
import json
import pytest
from pathlib import Path
from src.synthesis import (
    load_analysis_objects,
    escape_html,
    parse_dt,
)


# ── load_analysis_objects ──────────────────────────────────

class TestLoadAnalysisObjects:
    def test_reads_compact_jsonl(self, tmp_path):
        log = tmp_path / "analysis_log.jsonl"
        entry = {"title": "Test", "action": "Prepare/Monitor", "confidence": 3}
        log.write_text(json.dumps(entry) + "\n")
        result = load_analysis_objects(log)
        assert len(result) == 1
        assert result[0]["title"] == "Test"

    def test_multiple_entries(self, tmp_path):
        log = tmp_path / "analysis_log.jsonl"
        entries = [
            {"title": "A", "action": "Act"},
            {"title": "B", "action": "No Action"},
        ]
        log.write_text("\n".join(json.dumps(e) for e in entries) + "\n")
        result = load_analysis_objects(log)
        assert len(result) == 2
        assert result[0]["title"] == "A"
        assert result[1]["title"] == "B"

    def test_skips_narrative_lines(self, tmp_path):
        """Non-JSON lines (narrative text) are silently skipped."""
        log = tmp_path / "analysis_log.jsonl"
        log.write_text(
            json.dumps({"title": "Real entry", "action": "Act"}) + "\n"
            "1️⃣ What actually matters\n"
            "Some narrative text here.\n"
            "More narrative.\n"
        )
        result = load_analysis_objects(log)
        assert len(result) == 1
        assert result[0]["title"] == "Real entry"

    def test_skips_blank_lines(self, tmp_path):
        log = tmp_path / "analysis_log.jsonl"
        log.write_text(
            json.dumps({"title": "A"}) + "\n"
            "\n\n"
            + json.dumps({"title": "B"}) + "\n"
        )
        result = load_analysis_objects(log)
        assert len(result) == 2

    def test_skips_non_dict_json(self, tmp_path):
        """JSON arrays or primitives are not valid analysis entries."""
        log = tmp_path / "analysis_log.jsonl"
        log.write_text(
            "[1, 2, 3]\n"
            + json.dumps({"title": "Valid"}) + "\n"
        )
        result = load_analysis_objects(log)
        assert len(result) == 1
        assert result[0]["title"] == "Valid"

    def test_returns_empty_list_when_file_missing(self, tmp_path):
        result = load_analysis_objects(tmp_path / "nonexistent.jsonl")
        assert result == []

    def test_returns_empty_list_on_empty_file(self, tmp_path):
        log = tmp_path / "analysis_log.jsonl"
        log.write_text("")
        result = load_analysis_objects(log)
        assert result == []


# ── escape_html ────────────────────────────────────────────

class TestEscapeHtml:
    def test_escapes_angle_brackets(self):
        assert "&lt;" in escape_html("<script>")
        assert "&gt;" in escape_html("a > b")

    def test_escapes_ampersand(self):
        assert "&amp;" in escape_html("a & b")

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
