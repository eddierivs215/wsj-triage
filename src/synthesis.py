import argparse
import html
import json
import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta
from collections import Counter

log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent  # project root (parent of src/)

LOG    = BASE_DIR / "data" / "analysis_log.jsonl"
THEMES = BASE_DIR / "config" / "themes.json"
OUT_MD   = BASE_DIR / "output" / "weekly_memo.md"
OUT_HTML = BASE_DIR / "output" / "weekly_memo.html"


def parse_dt(s: str):
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def load_themes():
    if not THEMES.exists():
        return {"active_themes": []}
    try:
        obj = json.loads(THEMES.read_text(encoding="utf-8"))
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass
    return {"active_themes": []}


def load_analysis_objects(path: Path):
    """
    Reads analysis_log.jsonl returning a list of dict entries.

    The file must be compact JSON Lines (one JSON object per line), which is
    what server.py /save produces. Non-JSON lines (narrative text, blank lines,
    comments) are silently skipped — no rfind hacks.
    """
    items = []
    if not path.exists():
        return items
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            if isinstance(obj, dict):
                items.append(obj)
        except json.JSONDecodeError:
            pass  # skip narrative text, malformed lines
    return items


def pick_event_time(a: dict):
    return parse_dt(a.get("published_at", "")) or parse_dt(a.get("created_at", ""))


def escape_html(s: str) -> str:
    return html.escape(s or "")


def md_to_basic_html(md_text: str) -> str:
    """
    Lightweight Markdown-to-HTML renderer:
    - # / ## / ### headings
    - bullet lists starting with "- "
    - paragraphs
    Intentionally simple (no external deps).
    """
    lines = md_text.splitlines()
    html_lines = []
    in_ul = False

    def close_ul():
        nonlocal in_ul
        if in_ul:
            html_lines.append("</ul>")
            in_ul = False

    for line in lines:
        raw = line.rstrip("\n")
        if not raw.strip():
            close_ul()
            html_lines.append("<div style='height:8px'></div>")
            continue

        if raw.startswith("### "):
            close_ul()
            html_lines.append(f"<h3>{escape_html(raw[4:])}</h3>")
            continue
        if raw.startswith("## "):
            close_ul()
            html_lines.append(f"<h2>{escape_html(raw[3:])}</h2>")
            continue
        if raw.startswith("# "):
            close_ul()
            html_lines.append(f"<h1>{escape_html(raw[2:])}</h1>")
            continue

        if raw.startswith("- "):
            if not in_ul:
                html_lines.append("<ul>")
                in_ul = True
            html_lines.append(f"<li>{escape_html(raw[2:])}</li>")
            continue

        # default paragraph
        close_ul()
        html_lines.append(f"<p>{escape_html(raw)}</p>")

    close_ul()

    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Weekly WSJ Signal Memo</title>
<style>
  body {{ font-family: -apple-system, system-ui, Arial; margin: 24px; line-height: 1.4; }}
  h1 {{ font-size: 22px; margin: 0 0 14px; }}
  h2 {{ font-size: 16px; margin: 18px 0 8px; }}
  h3 {{ font-size: 14px; margin: 14px 0 6px; }}
  p, li {{ font-size: 13px; }}
  code {{ background: rgba(0,0,0,.06); padding: 2px 6px; border-radius: 6px; }}
  ul {{ margin: 6px 0 10px 18px; }}
</style>
</head>
<body>
{''.join(html_lines)}
</body>
</html>
"""


def main(days: int = 7):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")

    # Ensure directories exist
    (BASE_DIR / "data").mkdir(parents=True, exist_ok=True)
    (BASE_DIR / "output").mkdir(parents=True, exist_ok=True)

    now      = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=days)

    analyses = load_analysis_objects(LOG)

    # Filter to the requested window
    recent = []
    for a in analyses:
        dt = pick_event_time(a)
        if dt and dt >= week_ago:
            recent.append((dt, a))
    recent.sort(key=lambda x: x[0])

    themes = load_themes().get("active_themes", [])

    reinforce  = Counter()
    contradict = Counter()
    tags       = Counter()

    # Stance-change tracking (monotonic escalation vs flip-flop — caller interprets)
    stance_changes: list = []
    last_action_by_key: dict = {}

    confidence_changes: list = []

    # Collect Act items for the top-of-memo callout
    act_items: list = []

    for dt, a in recent:
        for t in (a.get("tags", []) or []):
            tags[str(t)] += 1

        for th in (a.get("reinforces", []) or []):
            reinforce[str(th)] += 1

        for th in (a.get("contradicts", []) or []):
            contradict[str(th)] += 1

        keys: list = []
        keys.extend([str(x) for x in (a.get("reinforces", []) or []) if x])
        keys.extend([str(x) for x in (a.get("tags", []) or []) if x])

        for key in keys:
            prev = last_action_by_key.get(key)
            curr = a.get("action")
            if prev and curr and prev != curr:
                stance_changes.append((dt.isoformat(), key, prev, curr, a.get("title", "")))
            if curr:
                last_action_by_key[key] = curr

        if a.get("updates_confidence"):
            confidence_changes.append((dt.isoformat(), str(a.get("updates_confidence")), a.get("title", "")))

        if a.get("action") == "Act":
            act_items.append((dt, a))

    # Sort Act items: most recent first, then highest confidence within same timestamp
    act_items.sort(
        key=lambda x: (x[0], int(x[1].get("confidence", 0) or 0)),
        reverse=True,
    )

    lines = []
    lines.append("# Weekly WSJ Signal Memo\n")
    lines.append(f"- Window: last {days} days (generated {now.isoformat()})")
    lines.append(f"- Log source: {LOG.name}")
    lines.append(f"- Parsed entries (last {days}d): {len(recent)}\n")

    # ── Act items — first, most urgent ───────────────────────────────────────
    lines.append("## Act items\n")
    if act_items:
        for dt, a in act_items:
            lines.append(f"- {dt.isoformat()} — **{a.get('title', '')}** ({a.get('category', '')})")
            for trigger in (a.get("action_triggers", []) or []):
                lines.append(f"  - Trigger: {trigger}")
    else:
        lines.append(f"- No 'Act' items in the last {days} days.")

    # ── Theme reinforcement ───────────────────────────────────────────────────
    lines.append("\n## Theme reinforcement\n")
    if reinforce:
        for name, cnt in reinforce.most_common(10):
            contra = contradict.get(name, 0)
            lines.append(f"- **{name}**: +{cnt} reinforcements, {contra} contradictions")
    else:
        lines.append("- No reinforcements recorded (or no valid JSON entries).")

    lines.append("\n## Active theme checklist (from themes.json)\n")
    if themes:
        for t in themes:
            name    = t.get("name", "(unnamed)")
            thesis  = t.get("thesis", "")
            lines.append(f"- **{name}** — {thesis}")
            triggers = t.get("watch_triggers", []) or []
            if triggers:
                lines.append(f"  - Triggers: {', '.join(triggers)}")
    else:
        lines.append("- No active themes configured.")

    # ── Stance changes ────────────────────────────────────────────────────────
    lines.append("\n## Stance changes\n")
    lines.append("_(monotonic escalation = thesis developing; back-and-forth = reassess the thesis)_\n")
    if stance_changes:
        for ts, key, prev, curr, title in stance_changes[:30]:
            lines.append(f"- {ts} — **{key}**: {prev} → {curr} ({title})")
    else:
        lines.append(f"- No stance changes detected in the last {days} days.")

    lines.append("\n## Confidence updates\n")
    if confidence_changes:
        for ts, delta, title in confidence_changes[:30]:
            lines.append(f"- {ts} — {delta} ({title})")
    else:
        lines.append("- No explicit confidence updates recorded.")

    lines.append("\n## Tag frequency\n")
    if tags:
        for tag, cnt in tags.most_common(15):
            lines.append(f"- {tag}: {cnt}")
    else:
        lines.append("- No tags recorded.")

    md_text = "\n".join(lines) + "\n"

    OUT_MD.write_text(md_text, encoding="utf-8")
    OUT_HTML.write_text(md_to_basic_html(md_text), encoding="utf-8")

    log.info("Parsed %d entries from last %d days", len(recent), days)
    log.info("Wrote %s", OUT_MD.resolve())
    log.info("Wrote %s", OUT_HTML.resolve())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate WSJ Signal weekly memo")
    parser.add_argument("--days", type=int, default=7, help="Analysis window in days (default: 7)")
    args = parser.parse_args()
    main(days=args.days)
