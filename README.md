# wsj-triage

> v0.1.0 — Local-first research system for identifying durable, decision-relevant mechanisms in news.

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

**Action stances**: No Action, Monitor, Prepare, Act

---

## Design Constraints

| Principle | Implication |
|-----------|-------------|
| **Mechanism-first** | Extract *why* something matters, not *what* happened |
| **Triage ≠ Analysis** | Scoring what to read is separate from interpreting what it means; triage never emits "Act" |
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

This system has **two distinct run modes**:

### 1. Triage (file-based, no server required)

Generate the dashboard as a static HTML file:

```bash
python src/triage.py
# Output: output/triage.html
```

Open `output/triage.html` directly in a browser to review scored articles. The "Analyze" links will not work without the server running.

### 2. Analysis (requires Flask server)

To save analyses, the local server must be running:

```bash
python src/server.py
# → http://localhost:5050
```

The server provides:
- `GET /` — Serves the triage dashboard
- `GET /analyze` — Serves the analysis form (pre-filled from URL params)
- `GET /themes` — Returns active themes as JSON
- `POST /save` — Appends a JSON analysis to `data/analysis_log.jsonl`

**Workflow**: Dashboard → click "Analyze" → fill form → paste JSON from LLM → Save to log.

The analysis form uses relative fetch calls (`/save`, `/themes`) that require the Flask server.

---

## Repository Structure

```
wsj-triage/
├── README.md
├── requirements.txt
├── .gitignore
├── migrate.sh              # One-time migration script
│
├── src/
│   ├── triage.py           # RSS fetch + heuristic scoring → dashboard
│   ├── synthesis.py        # Weekly memo from analysis log
│   └── server.py           # Local Flask server for analysis workflow
│
├── templates/
│   └── analyze.html        # Manual analysis form UI
│
├── config/
│   └── themes.json         # Active themes + watch triggers
│
├── data/                   # Persistent state (human-managed analyses)
│   ├── analysis_log.jsonl  # Append-only log of manual analyses
│   ├── url_first_seen.json # URL → first-seen timestamp (evergreen detection)
│   └── run_state.json      # Last run timestamp + URLs (new item detection)
│
├── output/                 # Generated artifacts (gitignored)
│   ├── triage.html         # Generated dashboard
│   ├── weekly_memo.md      # Generated synthesis
│   └── weekly_memo.html
│
└── examples/
    └── analysis_entry.json # Schema reference
```

---

## Workflow

```
┌─────────────────────────────────────────────────────────────────────────┐
│  1. TRIAGE (automated)                                                  │
│     python src/triage.py                                                │
│     → Fetches RSS, scores articles, writes output/triage.html           │
└─────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────┐
│  2. READ (manual)                                                       │
│     Open dashboard, filter by signal strength, read high-signal items   │
└─────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────┐
│  3. ANALYZE (manual, requires server)                                   │
│     python src/server.py                                                │
│     Click "Analyze" → Generate prompt → Run in LLM → Paste JSON → Save  │
│     → Appends to data/analysis_log.jsonl                                │
└─────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────┐
│  4. SYNTHESIZE (automated)                                              │
│     python src/synthesis.py                                             │
│     → Reads analysis_log.jsonl, writes weekly_memo.md/.html             │
└─────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────┐
│  5. REFLECT (manual)                                                    │
│     Review memo: theme reinforcements, contradictions, action flips     │
│     Update themes.json if convictions change                            │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Analysis Schema

Each entry in `data/analysis_log.jsonl` is a JSON object (one per line):

```json
{
  "title": "Article headline",
  "source": "WSJ",
  "category": "Earnings | Policy/Regulatory | Structural | Markets | Geopolitics | Cyclical | Narrative/Opinion | Noise",
  "signal_strength": "High | Medium | Low",
  "time_horizon": "Immediate | Near-term | Structural",
  "signal_bullets": ["Key fact 1", "Key fact 2"],
  "mechanism": "The causal chain that makes this matter",
  "base_case": "Most likely outcome given this signal",
  "tail_risk": "Low-probability but consequential alternative",
  "action": "No Action | Monitor | Prepare | Act",
  "action_triggers": ["What would change the action stance"],
  "confidence": 1-5,
  "tags": ["topic1", "topic2"],
  "reinforces": ["theme or prior view this supports"],
  "contradicts": ["theme or prior view this challenges"],
  "updates_confidence": "How this changes conviction on a thesis"
}
```

See `examples/analysis_entry.json` for a complete example.

---

## Setup

```bash
# Clone and enter directory
cd wsj-triage

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt

# (If migrating from flat structure) Run migration
chmod +x migrate.sh && ./migrate.sh
```

---

## Quick Start

```bash
# 1. Generate triage dashboard
python src/triage.py

# 2. Start server for analysis workflow
python src/server.py &

# 3. Open dashboard
open http://localhost:5050  # or visit in browser

# 4. (After logging analyses) Generate weekly memo
python src/synthesis.py
```

---

## Themes

Edit `config/themes.json` to define the persistent forces you're tracking:

```json
{
  "active_themes": [
    {
      "name": "AI infrastructure constraints",
      "thesis": "AI growth is bounded by electricity, copper, and memory supply",
      "watch_triggers": ["project delays", "supply lock-ins", "grid constraints"]
    }
  ]
}
```

Themes appear in:
- The dashboard header (active themes loaded)
- The analysis prompt (for LLM context)
- The weekly memo (reinforcements/contradictions)

---

## Success Criterion

Over time, this tool should help you:

- **Read less, miss less** — High-signal filtering reduces noise
- **Form conviction from evidence** — Structured analyses accumulate
- **Understand why views changed** — Longitudinal memory makes shifts visible

---

## License

Private use.
