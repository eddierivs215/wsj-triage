import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, request, jsonify, make_response, send_file

log = logging.getLogger(__name__)

app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent  # project root (parent of src/)
LOG_FILE = BASE_DIR / "data" / "analysis_log.jsonl"
THEMES_FILE = BASE_DIR / "config" / "themes.json"
TRIAGE_FILE = BASE_DIR / "output" / "triage.html"
ANALYZE_FILE = BASE_DIR / "templates" / "analyze.html"

# Ensure data directory exists for /save endpoint
(BASE_DIR / "data").mkdir(parents=True, exist_ok=True)


def no_cache(resp):
    resp.headers["Cache-Control"] = "no-store"
    return resp


@app.get("/")
def home():
    resp = make_response(send_file(TRIAGE_FILE, mimetype="text/html"))
    return no_cache(resp)


@app.get("/analyze")
def analyze():
    resp = make_response(send_file(ANALYZE_FILE, mimetype="text/html"))
    resp.headers["Content-Type"] = "text/html; charset=utf-8"
    resp.headers["Cache-Control"] = "no-store"
    return resp


@app.get("/themes")
def themes():
    if THEMES_FILE.exists():
        resp = make_response(send_file(THEMES_FILE, mimetype="application/json"))
        return no_cache(resp)
    return jsonify({"active_themes": []})


@app.post("/save")
def save():
    try:
        obj = request.get_json(force=True)
    except Exception:
        return jsonify({"ok": False, "error": "Invalid JSON"}), 400

    if not isinstance(obj, dict):
        return jsonify({"ok": False, "error": "Payload must be a JSON object"}), 400

    # Reject triage-only fields — schema bleed prevention.
    # triage_decision belongs only in the triage pipeline; analysis payloads use 'action'.
    TRIAGE_ONLY_FIELDS = {"triage_decision"}
    leaked = [k for k in obj if k in TRIAGE_ONLY_FIELDS]
    if leaked:
        return jsonify({
            "ok": False,
            "error": f"triage_decision is a triage-only field and must not appear in analysis payloads. Use 'action' instead.",
        }), 400

    # Minimal required keys
    required = ["title", "source", "category", "signal_strength", "time_horizon", "action", "confidence"]
    missing = [k for k in required if k not in obj]
    if missing:
        return jsonify({"ok": False, "error": f"Missing keys: {missing}"}), 400

    # Validate enum fields — error messages include the full set of allowed values
    VALID_ENUMS = {
        "category":        ["Policy/Regulatory", "Earnings", "Geopolitics", "Markets", "Structural", "Cyclical", "Narrative/Opinion", "Noise"],
        "signal_strength": ["High", "Medium", "Low"],
        "time_horizon":    ["Immediate", "Near-term", "Structural"],
        "action":          ["Act", "Prepare/Monitor", "No Action"],
    }
    for field, allowed in VALID_ENUMS.items():
        val = obj.get(field)
        if val not in allowed:
            return jsonify({"ok": False, "error": f"Invalid {field}: {val!r}. Allowed values: {allowed}"}), 400

    obj["server_received_at"] = datetime.now(timezone.utc).isoformat()

    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")

    log.info("Saved analysis: %s", obj.get("title", "(untitled)"))
    return jsonify({"ok": True})


@app.get("/analyses")
def analyses():
    ANALYSES_FILE = BASE_DIR / "templates" / "analyses.html"
    resp = make_response(send_file(ANALYSES_FILE, mimetype="text/html"))
    resp.headers["Content-Type"] = "text/html; charset=utf-8"
    resp.headers["Cache-Control"] = "no-store"
    return resp


@app.get("/api/analyses")
def api_analyses():
    items = []
    if LOG_FILE.exists():
        for line in LOG_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if isinstance(obj, dict):
                    items.append(obj)
            except Exception:
                continue
    return jsonify(items)


_ANALYSIS_SCHEMA = """{
  "title": "",
  "source": "WSJ",
  "published_at": "",
  "category": "Structural | Cyclical | Policy/Regulatory | Earnings | Geopolitics | Markets | Narrative/Opinion | Noise",
  "signal_strength": "High | Medium | Low",
  "time_horizon": "Immediate | Near-term | Structural",
  "signal_bullets": ["", ""],
  "mechanism": "",
  "base_case": "",
  "tail_risk": "",
  "action": "Act | Prepare/Monitor | No Action",
  "action_triggers": ["", ""],
  "confidence": 1,
  "tags": [],
  "reinforces": [],
  "contradicts": [],
  "updates_confidence": ""
}"""

_ANALYSIS_PROMPT_TEMPLATE = """\
You are an analyst. Return TWO outputs in this exact order:
(1) One JSON object that strictly matches the schema below.
(2) A six-section narrative write-up.

Schema:
{schema}

Rules:
- High signal if any of: new policy with enforcement/timeline; earnings results/guidance; physical constraints; financing conditions shifting.
- Low signal if: "stocks rose/fell" with no new catalyst; optics/personality story; opinion without new facts.
- Action = Act only if mechanism is direct AND horizon is immediate/medium AND you can name 1-3 concrete triggers. Otherwise Prepare/Monitor or No Action.
- Spell out acronyms on first use, then include the acronym in parentheses.
- Be conservative.

Six-section format (exact headings):
1. What actually matters in this article (distilled)
2. The critical mechanism (this is the insight)
3. This connects directly to your other themes
4. Why this matters for inflation (non-obvious but important)
5. Does this change the action stance?
6. Your clean log entry (ready to save)

URL: {url}
Headline: {title}

Active themes:
{themes}

Article text:
\"\"\"{article}\"\"\"\
"""


def _parse_analysis_response(text: str):
    """Extract the first JSON object and trailing narrative from a model response."""
    decoder = json.JSONDecoder()
    start = text.find("{")
    if start == -1:
        raise ValueError("No JSON object found in response")
    obj, end_idx = decoder.raw_decode(text, start)
    if not isinstance(obj, dict):
        raise ValueError("Parsed value is not a JSON object")
    narrative = text[end_idx:].strip()
    return obj, narrative


@app.post("/api/analyze")
def api_analyze():
    try:
        import anthropic as _anthropic
    except ImportError:
        return jsonify({"ok": False, "error": "anthropic package not installed. Run: pip install anthropic"}), 503

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return jsonify({"ok": False, "error": "ANTHROPIC_API_KEY environment variable is not set"}), 503

    body = request.get_json(force=True) or {}
    url     = body.get("url", "")
    title   = body.get("title", "")
    article = body.get("article", "")
    themes  = body.get("themes", {"active_themes": []})

    if not article.strip():
        return jsonify({"ok": False, "error": "article text is required"}), 400

    prompt = _ANALYSIS_PROMPT_TEMPLATE.format(
        schema=_ANALYSIS_SCHEMA,
        url=url,
        title=title,
        themes=json.dumps(themes, indent=2),
        article=article,
    )

    try:
        client = _anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        response_text = message.content[0].text
    except Exception as e:
        return jsonify({"ok": False, "error": f"Claude API error: {e}"}), 502

    try:
        analysis, narrative = _parse_analysis_response(response_text)
    except Exception as e:
        return jsonify({"ok": False, "error": f"Could not parse JSON from response: {e}", "raw": response_text}), 422

    return jsonify({"ok": True, "analysis": analysis, "narrative": narrative})


if __name__ == "__main__":
    # Local only
    app.run(host="127.0.0.1", port=5050, debug=True)
