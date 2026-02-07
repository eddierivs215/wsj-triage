"""Tests for triage scoring, classification, and helpers."""
import pytest
from src.triage import (
    score_item,
    classify_category,
    classify_categories,
    signal_strength,
    time_horizon,
    confidence,
    strip_html,
)


# ── score_item ──────────────────────────────────────────────

class TestScoreItem:
    def test_baseline_score(self):
        score, _, _ = score_item("Generic headline", "Some summary", "WSJ")
        assert score == 50

    def test_numeric_boost(self):
        score, reasons, _ = score_item("Revenue rose 12%", "", "WSJ")
        assert score > 50
        assert any("quantitative" in r.lower() for r in reasons)

    def test_market_move_penalty(self):
        score, reasons, _ = score_item("Stocks rose sharply", "", "WSJ")
        assert score < 50
        assert any("market-move" in r.lower() for r in reasons)

    def test_framing_penalty(self):
        score, reasons, _ = score_item("Opinion: why markets matter", "", "WSJ")
        assert score < 50

    def test_opinion_source_penalty(self):
        score, _, _ = score_item("Something", "", "WSJ Opinion")
        assert score < 50

    def test_score_clamped_to_range(self):
        # Stack multiple penalties
        score, _, _ = score_item(
            "Opinion: stocks fell, could might may risk",
            "",
            "WSJ Opinion",
        )
        assert 0 <= score <= 100

    def test_high_signal_category_boost(self):
        score, reasons, _ = score_item("Fed raises rates by 25bps", "", "WSJ")
        assert score > 50
        assert any("category" in r.lower() for r in reasons)

    def test_theme_trigger_boost(self):
        themes = [{"name": "AI infra", "watch_triggers": ["grid interconnection constraints"]}]
        score, reasons, matched = score_item(
            "Grid interconnection constraints delay data center projects", "", "WSJ",
            theme_triggers=themes,
        )
        assert "AI infra" in matched
        assert any("theme match" in r.lower() for r in reasons)
        # Should score higher than baseline
        baseline, _, _ = score_item(
            "Grid interconnection constraints delay data center projects", "", "WSJ",
        )
        assert score > baseline

    def test_no_theme_match(self):
        themes = [{"name": "AI infra", "watch_triggers": ["HBM allocation"]}]
        score, _, matched = score_item("Weather forecast sunny", "", "WSJ", theme_triggers=themes)
        assert matched == []


# ── classify_category ──────────────────────────────────────

class TestClassifyCategory:
    def test_policy(self):
        assert classify_category("Fed raises rates", "") == "Policy/Regulatory"

    def test_earnings(self):
        assert classify_category("Apple earnings beat", "") == "Earnings"

    def test_geopolitics(self):
        assert classify_category("Ukraine conflict escalates", "") == "Geopolitics"

    def test_markets(self):
        assert classify_category("Bond yields surge", "") == "Markets"

    def test_structural(self):
        assert classify_category("Data center capacity crunch", "") == "Structural"

    def test_opinion_framing(self):
        assert classify_category("Opinion: what it means for you", "") == "Narrative/Opinion"

    def test_default_cyclical(self):
        assert classify_category("Weather forecast for weekend", "") == "Cyclical"

    def test_multi_category(self):
        # "Fed tariff" matches Policy, "semiconductor" matches Structural
        cats = classify_categories("Fed tariff on semiconductor imports", "")
        assert "Policy/Regulatory" in cats
        assert "Structural" in cats
        assert len(cats) >= 2
        # Primary should be first rule match (Policy/Regulatory)
        assert cats[0] == "Policy/Regulatory"

    def test_single_category_returns_list(self):
        cats = classify_categories("Weather forecast for weekend", "")
        assert cats == ["Cyclical"]


# ── signal_strength ────────────────────────────────────────

class TestSignalStrength:
    def test_high(self):
        assert signal_strength(70) == "High"
        assert signal_strength(100) == "High"

    def test_medium(self):
        assert signal_strength(45) == "Medium"
        assert signal_strength(69) == "Medium"

    def test_low(self):
        assert signal_strength(0) == "Low"
        assert signal_strength(44) == "Low"


# ── time_horizon ───────────────────────────────────────────

class TestTimeHorizon:
    def test_immediate(self):
        assert time_horizon("Earnings") == "Immediate"
        assert time_horizon("Markets") == "Immediate"
        assert time_horizon("Policy/Regulatory") == "Immediate"

    def test_structural(self):
        assert time_horizon("Structural") == "Structural"

    def test_near_term_default(self):
        assert time_horizon("Cyclical") == "Near-term"
        assert time_horizon("Geopolitics") == "Near-term"
        assert time_horizon("Noise") == "Near-term"


# ── confidence ─────────────────────────────────────────────

class TestConfidence:
    def test_range(self):
        assert confidence(100) == 5
        assert confidence(85) == 5
        assert confidence(70) == 4
        assert confidence(55) == 3
        assert confidence(40) == 2
        assert confidence(0) == 1


# ── strip_html ─────────────────────────────────────────────

class TestStripHtml:
    def test_removes_tags(self):
        assert strip_html("<p>Hello <b>world</b></p>") == "Hello world"

    def test_handles_none(self):
        assert strip_html("") == ""
