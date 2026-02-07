import json
import logging
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

    # Minimal required keys (adjust if you want stricter enforcement)
    required = ["title", "source", "category", "signal_strength", "time_horizon", "action", "confidence"]
    missing = [k for k in required if k not in obj]
    if missing:
        return jsonify({"ok": False, "error": f"Missing keys: {missing}"}), 400

    # Validate enum fields
    VALID_ENUMS = {
        "category": ["Policy/Regulatory", "Earnings", "Geopolitics", "Markets", "Structural", "Cyclical", "Narrative/Opinion", "Noise"],
        "signal_strength": ["High", "Medium", "Low"],
        "time_horizon": ["Immediate", "Near-term", "Structural"],
        "action": ["Act", "Prepare/Monitor", "No Action"],
    }
    for field, allowed in VALID_ENUMS.items():
        val = obj.get(field)
        if val not in allowed:
            return jsonify({"ok": False, "error": f"Invalid {field}: {val!r}. Allowed: {allowed}"}), 400

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


if __name__ == "__main__":
    # Local only
    app.run(host="127.0.0.1", port=5050, debug=True)
