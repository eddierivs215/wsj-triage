# wsj-triage

> v0.3.0 — Local-first research system for identifying durable, decision-relevant mechanisms in news.

Not a news summarizer. Not a trading system. A tool for reading less while missing less.

---

## Goal

Surface and track **persistent forces**—constraints, incentives, policy enforcement, earnings dynamics, market structure changes—across time horizons.

Reduce attention waste. Increase conviction from evidence. Understand why views change over time.

## Non-Goals

- Real-time alerting or trade execution
- Pure summarization or narrative aggregation
- Inflation-first or any specific macro framing
- Paywall scraping or content extraction
- Scale, speed, or ML complexity

---

## Conceptual Flow

```
News → Mechanism → Impact Vectors → Time Horizon → Action Stance → Memory
       ─────────────────────────────────────────────────────────────────
       "What force    "Where does    "When does     "What do I    "Track it
        is at work?"   it hit?"       it matter?"    do now?"      over time"
```

**Impact vectors** (examples):
- Costs / pricing power
- Capacity / physical constraints
- Capital allocation / financing conditions
- Market structure / liquidity
- Volatility / tail risk
- Distributional effects

**Time horizons**: Immediate, Near-term, Structural

**Action stances (analysis only)**: No Action, Prepare/Monitor, Act

---

## Design Constraints

| Principle | Implication |
|-----------|-------------|
| **Mechanism-first** | Extract *why* something matters, not *what* happened |
| **Triage ≠ Analysis** | Triage decides Read vs Skip only; it never emits "Act" — that requires deep-dive analysis |
| **Human-in-the-loop** | All analyses are manually created; automation supports, never replaces, judgment |
| **Longitudinal memory** | URL history, analysis log, and themes persist across sessions |
| **Explainability** | Heuristic scoring with visible rules; no opaque models |
| **Debuggability** | Flat files (JSON/JSONL), no database, inspectable state |

---

## What Is Automated vs Manual

### Safe to Automate

| Component | What it does | Why it's safe |
|-----------|--------------|---------------|
| `triage.py` | Fetches RSS, scores articles, generates dashboard | Heuristic scoring with explicit, inspectable rules; no interpretation |
| `synthesis.py` | Aggregates existing analyses into weekly memo | Summarizes *your* prior judgments; adds no new claims |
| URL memory | Tracks first-seen dates, flags evergreen items | Mechanical bookkeeping |
| Dashboard generation | Renders scored items as filterable HTML | Pure presentation |

### Intentionally Manual

| Component | What it requires | Why it must stay manual |
|-----------|------------------|------------------------|
| **Reading articles** | Human attention | Judgment on relevance, framing, source quality |
| **Analysis creation** | Mechanism identification, time horizon, action stance | Core intellectual work; cannot be delegated |
| **Theme definition** | Thesis + watch triggers in `themes.json` | Encodes your worldview; must reflect your convictions |
| **Interpretation** | Acting on weekly memo patterns | Synthesis shows patterns; you decide what they mean |

---

## Run Modes

All commands go through the unified `run.py` entry point.

### 1. Triage

Fetch RSS, score articles, write the dashboard:

```bash
python run.py triage
# Output: output/triage.html
```

> **Note**: The dashboard's "Analyze" links use relative paths (`/analyze?...`) and only work when the server is running. Opening `output/triage.html` directly as a file will display the dashboard but those links won't work.

### 2. Analysis (requires Flask server)

```bash
python run.py serve          # default port 5050
python run.py serve --port 8080
# → http://localhost:5050
```

The server provides:
- `GET /` — Serves the triage dashboard (regenerate first with `python run.py triage`)
- `GET /analyze` — Analysis form, pre-filled from URL params
- `GET /analyses` — Browse the analysis log
- `GET /themes` — Active themes as JSON
- `POST /save` — Appends a validated JSON analysis to `data/analysis_log.jsonl`

**Workflow**: `python run.py triage` → `python run.py serve` → open dashboard → filter to Read items → click "Analyze" → generate prompt → run in LLM → paste JSON → Save.

### 3. Synthesis

```bash
python run.py synthesis          # default: last 7 days
python run.py synthesis --days 14
# Output: output/weekly_memo.md, output/weekly_memo.html
```

---

## Repository Structure

```
wsj-triage/
├── README.md
├── requirements.txt
├── run.py                  # Unified CLI entry point
├── .gitignore
│
├── src/
│   ├── triage.py           # RSS fetch + heuristic scoring → dashboard
│   ├── synthesis.py        # Weekly memo from analysis log
│   └── server.py           # Local Flask server for analysis workflow
│
├── templates/
│   ├── analyze.html        # Manual analysis form UI
│   └── analyses.html       # Analysis log browser
│
├── config/
│   ├── themes.json         # Active themes + watch triggers + keywords
│   └── scoring.json        # Tunable score thresholds (no code edits needed)
│
├── data/                   # Persistent state (human-managed analyses)
│   ├── analysis_log.jsonl  # Append-only log of manual analyses (compact JSON Lines)
│   ├── url_first_seen.json # URL → first-seen timestamp (evergreen detection)
│   └── run_state.json      # Last run timestamp + URLs (new item detection)
│
├── output/                 # Generated artifacts (gitignored)
│   ├── triage.html         # Generated dashboard
│   ├── weekly_memo.md      # Generated synthesis
│   └── weekly_memo.html
│
├── tests/
│   ├── test_triage.py      # Scoring, classification, triage decision
│   ├── test_synthesis.py   # JSONL loading, helpers
│   └── test_server.py      # /save validation, enum enforcement
│
└── examples/
    └── analysis_entry.json # Schema reference
```

---

## Workflow

```
┌─────────────────────────────────────────────────────────────────────────┐
│  1. TRIAGE (automated)                                                  │
│     python run.py triage                                                │
│     → Fetches RSS, scores articles, writes output/triage.html           │
│     → Logs calibration: High/Medium/Low % and Read/Skip counts          │
└─────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────┐
│  2. READ (manual)                                                       │
│     python run.py serve → open http://localhost:5050                    │
│     Filter to "Read" decisions; skip Low-signal / Noise items           │
└─────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────┐
│  3. ANALYZE (manual, requires server)                                   │
│     Click "Analyze" → Generate prompt → Run in LLM → Paste JSON → Save │
│     → Appends to data/analysis_log.jsonl                                │
└─────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────┐
│  4. SYNTHESIZE (automated)                                              │
│     python run.py synthesis                                             │
│     → Reads analysis_log.jsonl, writes weekly_memo.md/.html             │
│     → Opens with "Act items" section; tracks stance changes over time   │
└─────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────┐
│  5. REFLECT (manual)                                                    │
│     Review memo: Act items, theme reinforcements, stance changes        │
│     Update themes.json if convictions change                            │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Triage vs Analysis: Two Distinct Contracts

The system enforces a hard boundary between what triage produces and what analysis records.

### Triage output (`triage.py` → dashboard)

| Field | Values | Notes |
|-------|--------|-------|
| `signal_strength` | `High \| Medium \| Low` | Derived from heuristic score |
| `triage_decision` | `Read \| Skip` | The only output that matters for workflow |
| `time_horizon` | `Immediate \| Near-term \| Structural` | Text-cue + category default |
| `confidence` | 1–5 | Derived from score; not a human judgment |
| `mechanism` | *(empty)* | Populated only in the analysis stage |

Triage **never** emits `Act` or a mechanism. Doing so would claim interpretation that hasn't happened.

### Analysis log (`data/analysis_log.jsonl`)

Each entry is a compact JSON object (one per line). The server rejects any payload containing `triage_decision` — the two schemas must not bleed into each other.

```json
{
  "title": "Article headline",
  "source": "WSJ",
  "published_at": "2026-01-15T10:00:00+00:00",
  "category": "Earnings | Policy/Regulatory | Structural | Markets | Geopolitics | Cyclical | Narrative/Opinion | Noise",
  "signal_strength": "High | Medium | Low",
  "time_horizon": "Immediate | Near-term | Structural",
  "signal_bullets": ["Key fact 1", "Key fact 2"],
  "mechanism": "The causal chain that makes this matter",
  "base_case": "Most likely outcome given this signal",
  "tail_risk": "Low-probability but consequential alternative",
  "action": "No Action | Prepare/Monitor | Act",
  "action_triggers": ["What would change the action stance"],
  "confidence": 3,
  "tags": ["topic1", "topic2"],
  "reinforces": ["theme or prior view this supports"],
  "contradicts": ["theme or prior view this challenges"],
  "updates_confidence": "How this changes conviction on a thesis"
}
```

See `examples/analysis_entry.json` for a complete example.

---

## Scoring

Scores are computed in `triage.py` via additive heuristics. Thresholds are in `config/scoring.json` and tunable without code edits.

**Default thresholds:**

| Band | Score |
|------|-------|
| High | ≥ 62 |
| Medium | ≥ 45 |
| Low | < 45 |

**Score components (baseline = 35):**

| Signal | Δ Score |
|--------|---------|
| Quantitative data present | +12 |
| High-signal category (Policy/Regulatory, Earnings, Structural) | +12 |
| Theme phrase match (`watch_triggers`) | +8 |
| Theme keyword match (`keywords_any`, requires 2 hits or headline+body) | +5 |
| Market-move headline ("stocks rose/fell") | −18 |
| Framing/explainer language ("opinion", "why", "how to") | −14 |
| Opinion source | −20 |
| Hedging/modality language ("could", "might", "fears") | −4 |

**Calibration**: Every run logs `Signal bands — High:N (X%)  Medium:N (X%)  Low:N (X%)` and `Triage decisions — Read:N  Skip:N`. If Medium dominates, lower `high_threshold` in `config/scoring.json`.

---

## Themes

Edit `config/themes.json` to define the persistent forces you're tracking:

```json
{
  "active_themes": [
    {
      "name": "AI infrastructure constraints",
      "thesis": "AI growth is bounded by electricity, copper, and memory supply",
      "watch_triggers": [
        "grid interconnection constraints",
        "HBM allocation headlines"
      ],
      "keywords_any": [
        "HBM", "interconnect", "grid constraint",
        "data center capacity", "chip shortage"
      ]
    }
  ]
}
```

**Matching logic**: `watch_triggers` are matched as exact phrases (higher precision, +8 score). `keywords_any` are matched as individual tokens but require **2 distinct hits** anywhere in the text, or **1 hit in the headline + 1 anywhere** (+5 score). This prevents single generic keywords from firing false positives.

Themes appear in:
- The dashboard header (active themes loaded)
- The analysis prompt (for LLM context)
- The weekly memo (reinforcements/contradictions)

---

## Setup

```bash
cd wsj-triage

python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

pip install -r requirements.txt

# Run tests
python -m pytest tests/ -v
```

---

## Quick Start

```bash
# 1. Generate triage dashboard
python run.py triage

# 2. Start server
python run.py serve

# 3. Open dashboard in browser
open http://localhost:5050

# 4. (After logging analyses) Generate weekly memo
python run.py synthesis
```

---

## Success Criterion

Over time, this tool should help you:

- **Read less, miss less** — High-signal filtering reduces noise
- **Form conviction from evidence** — Structured analyses accumulate
- **Understand why views changed** — Longitudinal memory makes shifts visible

---

## License

Private use.
