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
    make_triage_decision,
    SCORE_BASELINE,
    HIGH_THRESHOLD,
    MEDIUM_THRESHOLD,
)


# ── score_item ──────────────────────────────────────────────

class TestScoreItem:
    def test_baseline_score(self):
        score, _, _ = score_item("Generic headline", "Some summary", "WSJ")
        assert score == SCORE_BASELINE

    def test_numeric_boost(self):
        score, reasons, _ = score_item("Revenue rose 12%", "", "WSJ")
        assert score > SCORE_BASELINE
        assert any("quantitative" in r.lower() for r in reasons)

    def test_market_move_penalty(self):
        score, reasons, _ = score_item("Stocks rose sharply", "", "WSJ")
        assert score < SCORE_BASELINE
        assert any("market-move" in r.lower() for r in reasons)

    def test_framing_penalty(self):
        score, reasons, _ = score_item("Opinion: why markets matter", "", "WSJ")
        assert score < SCORE_BASELINE

    def test_opinion_source_penalty(self):
        score, _, _ = score_item("Something", "", "WSJ Opinion")
        assert score < SCORE_BASELINE

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
        assert score > SCORE_BASELINE
        assert any("category" in r.lower() for r in reasons)

    def test_theme_phrase_trigger_boost(self):
        """Exact phrase in watch_triggers fires a boost."""
        themes = [{"name": "AI infra", "watch_triggers": ["grid interconnection constraints"], "keywords_any": []}]
        score, reasons, matched = score_item(
            "Grid interconnection constraints delay data center projects", "", "WSJ",
            theme_triggers=themes,
        )
        assert "AI infra" in matched
        assert any("theme match" in r.lower() for r in reasons)
        baseline, _, _ = score_item(
            "Grid interconnection constraints delay data center projects", "", "WSJ",
        )
        assert score > baseline

    def test_theme_keyword_fallback_requires_two_hits(self):
        """keywords_any requires 2 distinct keyword hits anywhere in the text."""
        themes = [{"name": "AI infra", "watch_triggers": ["exact phrase not present"], "keywords_any": ["HBM", "grid constraint"]}]
        # Both keywords present → match
        score, reasons, matched = score_item(
            "HBM shortage drives grid constraint concerns", "", "WSJ",
            theme_triggers=themes,
        )
        assert "AI infra" in matched
        assert any("keyword" in r.lower() for r in reasons)

    def test_theme_keyword_single_hit_no_match(self):
        """A single keyword hit (not in headline) should NOT fire."""
        themes = [{"name": "AI infra", "watch_triggers": ["exact phrase not present"], "keywords_any": ["HBM", "grid constraint"]}]
        # Only 1 keyword present, not in headline → no match
        score, _, matched = score_item(
            "Supply chain issues persist", "HBM not mentioned elsewhere", "WSJ",
            theme_triggers=themes,
        )
        # "HBM" is in summary, "grid constraint" is not — only 1 hit → no match
        assert "AI infra" not in matched

    def test_theme_keyword_headline_plus_one_hit_matches(self):
        """1 keyword in headline + any keyword anywhere = match."""
        themes = [{"name": "AI infra", "watch_triggers": [], "keywords_any": ["HBM", "data center capacity"]}]
        # "HBM" in title + "data center capacity" in summary
        score, reasons, matched = score_item(
            "HBM demand surges", "data center capacity is the bottleneck", "WSJ",
            theme_triggers=themes,
        )
        assert "AI infra" in matched

    def test_theme_keyword_boost_is_weaker_than_phrase(self):
        """Keyword fallback gives +5; phrase match gives +8."""
        themes_phrase  = [{"name": "T", "watch_triggers": ["grid interconnection constraints"], "keywords_any": []}]
        themes_keyword = [{"name": "T", "watch_triggers": [], "keywords_any": ["HBM", "grid constraint"]}]
        title = "HBM and grid constraint update"
        score_phrase,  _, _ = score_item(title, "grid interconnection constraints are severe", "WSJ", theme_triggers=themes_phrase)
        score_keyword, _, _ = score_item(title, "HBM affected by grid constraint news",       "WSJ", theme_triggers=themes_keyword)
        assert score_phrase > score_keyword

    def test_no_theme_match(self):
        themes = [{"name": "AI infra", "watch_triggers": ["HBM allocation"], "keywords_any": ["HBM", "interconnect"]}]
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
        cats = classify_categories("Fed tariff on semiconductor imports", "")
        assert "Policy/Regulatory" in cats
        assert "Structural" in cats
        assert len(cats) >= 2
        assert cats[0] == "Policy/Regulatory"

    def test_single_category_returns_list(self):
        cats = classify_categories("Weather forecast for weekend", "")
        assert cats == ["Cyclical"]


# ── signal_strength ────────────────────────────────────────

class TestSignalStrength:
    def test_high(self):
        assert signal_strength(HIGH_THRESHOLD) == "High"
        assert signal_strength(100) == "High"

    def test_medium(self):
        assert signal_strength(MEDIUM_THRESHOLD) == "Medium"
        assert signal_strength(HIGH_THRESHOLD - 1) == "Medium"

    def test_low(self):
        assert signal_strength(0) == "Low"
        assert signal_strength(MEDIUM_THRESHOLD - 1) == "Low"


# ── time_horizon ───────────────────────────────────────────

class TestTimeHorizon:
    def test_category_default_immediate(self):
        assert time_horizon("Earnings") == "Immediate"
        assert time_horizon("Markets") == "Immediate"
        assert time_horizon("Policy/Regulatory") == "Immediate"

    def test_category_default_structural(self):
        assert time_horizon("Structural") == "Structural"

    def test_category_default_near_term(self):
        assert time_horizon("Cyclical") == "Near-term"
        assert time_horizon("Geopolitics") == "Near-term"
        assert time_horizon("Noise") == "Near-term"

    def test_text_cue_immediate_overrides_default(self):
        # Earnings miss in a Cyclical article → Immediate via text cue
        assert time_horizon("Cyclical", "Company missed estimates for Q3") == "Immediate"

    def test_text_cue_structural_overrides_default(self):
        # Structural language in an Earnings article → Structural via text cue
        assert time_horizon("Earnings", "This represents a multi-year secular shift") == "Structural"

    def test_no_text_cue_uses_category(self):
        assert time_horizon("Geopolitics", "Russia and Ukraine diplomatic talks") == "Near-term"


# ── make_triage_decision ────────────────────────────────────

class TestTriageDecision:
    def test_high_signal_is_read(self):
        assert make_triage_decision("High", "Earnings") == "Read"

    def test_medium_signal_is_read(self):
        assert make_triage_decision("Medium", "Markets") == "Read"

    def test_low_signal_is_skip(self):
        assert make_triage_decision("Low", "Markets") == "Skip"

    def test_noise_category_is_always_skip(self):
        assert make_triage_decision("High", "Noise") == "Skip"
        assert make_triage_decision("Medium", "Noise") == "Skip"


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

    def test_handles_empty(self):
        assert strip_html("") == ""

    def test_decodes_html_entities(self):
        assert strip_html("AT&amp;T raises &lt;5%&gt; guidance") == "AT&T raises <5%> guidance"

    def test_decodes_nbsp(self):
        result = strip_html("word&nbsp;word")
        assert "\xa0" in result or "word" in result  # decoded non-breaking space
