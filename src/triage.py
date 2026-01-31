import re
import json
import feedparser
from datetime import datetime, timezone, timedelta
from dateutil import parser as dateparser
from jinja2 import Template
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List

# =========================
# Configuration
# =========================

BASE_DIR = Path(__file__).resolve().parent.parent  # project root (parent of src/)

FEEDS = [
    "https://feeds.content.dowjones.io/public/rss/RSSWorldNews",      # World News
    "https://feeds.content.dowjones.io/public/rss/WSJcomUSBusiness",  # U.S. Business
    "https://feeds.content.dowjones.io/public/rss/RSSMarketsMain",    # Markets
    "https://feeds.content.dowjones.io/public/rss/socialeconomyfeed", # Economy
    "https://feeds.content.dowjones.io/public/rss/socialpoliticsfeed", # Politics

]

RECENT_HOURS = 48

CATEGORY_WINDOW_HOURS = {
    "Markets": 48,
    "Earnings": 72,
    "Policy/Regulatory": 168,   # 7 days
    "Geopolitics": 72,
    "Structural": 336,          # 14 days
    "Cyclical": 48,
    "Narrative/Opinion": 48,
    "Noise": 48,
}

RUN_STATE_FILE = BASE_DIR / "data" / "run_state.json"          # stores last run time + last run URLs
URL_AGE_FILE = BASE_DIR / "data" / "url_first_seen.json"       # for evergreen resurfacing badge
THEMES_FILE = BASE_DIR / "config" / "themes.json"              # optional context display on dashboard
EVERGREEN_DAYS = 90


# =========================
# Regex / Rules (light heuristics)
# =========================

NUMERIC = re.compile(r"\b(\d+(\.\d+)?%?|\$\d+|\d{4}|\bQ[1-4]\b)\b", re.I)

CATEGORY_RULES = [
    ("Policy/Regulatory", re.compile(r"\b(Fed|FOMC|Treasury|SEC|DOJ|FTC|regulat|rule|ban|tariff|sanction|bill|law|court|ruling|order)\b", re.I)),
    ("Earnings", re.compile(r"\b(earnings|guidance|EPS|revenue|profit|margin|10-?K|10-?Q|filing)\b", re.I)),
    ("Geopolitics", re.compile(r"\b(Iran|China|Russia|Ukraine|Israel|Gaza|Taiwan|NATO|war|conflict)\b", re.I)),
    ("Markets", re.compile(r"\b(yield|bond|rates|credit spread|dollar|FX|oil|WTI|Brent|copper|gold|equities|S&P|Nasdaq)\b", re.I)),
    ("Structural", re.compile(r"\b(capacity|supply chain|shortage|grid|electricity|data center|chip|semiconductor|copper|memory|HBM)\b", re.I)),
]

FRAMING_TERMS = re.compile(
    r"\b(opinion|column|what it means|explainer|why\b|how to|guide)\b",
    re.I,
)

MODAL_TERMS = re.compile(
    r"\b(could|might|may|risk|risks|fears|worries)\b",
    re.I,
)


LOW_SIGNAL_MARKET_MOVE = re.compile(
    r"\b(stocks (rose|fell)|shares (rose|fell)|market (rallied|slid))\b",
    re.I,
)


# =========================
# Helpers
# =========================

def window_hours_for_category(cat: str) -> int:
    return int(CATEGORY_WINDOW_HOURS.get(cat or "", RECENT_HOURS))


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def strip_html(text: str) -> str:
    return re.sub("<.*?>", "", text or "").strip()

def parse_rss_published_iso(entry) -> str:
    for key in ("published", "updated", "created"):
        val = entry.get(key)
        if val:
            try:
                dt = dateparser.parse(val)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.isoformat()
            except Exception:
                pass
    for key in ("published_parsed", "updated_parsed"):
        st = entry.get(key)
        if st:
            try:
                dt = datetime(*st[:6], tzinfo=timezone.utc)
                return dt.isoformat()
            except Exception:
                pass
    return ""

def is_recent(published_iso: str, hours: int = RECENT_HOURS) -> bool:
    if not published_iso:
        return False
    try:
        dt = dateparser.parse(published_iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        return dt >= cutoff
    except Exception:
        return False

def classify_category(title: str, summary: str) -> str:
    text = f"{title} {summary}"
    for cat, rx in CATEGORY_RULES:
        if rx.search(text):
            return cat
    if FRAMING_TERMS.search(text):
        return "Narrative/Opinion"
    return "Cyclical"

def signal_strength(score: int) -> str:
    if score >= 70:
        return "High"
    if score >= 45:
        return "Medium"
    return "Low"

def time_horizon(category: str) -> str:
    if category in ["Earnings", "Markets", "Policy/Regulatory"]:
        return "Immediate"
    if category in ["Structural"]:
        return "Structural"
    return "Medium"

def confidence(score: int) -> int:
    if score >= 85:
        return 5
    if score >= 70:
        return 4
    if score >= 55:
        return 3
    if score >= 40:
        return 2
    return 1

def score_item(title: str, summary: str, source: str) -> Tuple[int, List[str]]:
    text = f"{title} {summary}"
    score = 50
    reasons: List[str] = []

    if NUMERIC.search(text):
        score += 12
        reasons.append("Includes quantitative data")

    category = classify_category(title, summary)
    if category in ["Policy/Regulatory", "Earnings", "Structural"]:
        score += 12
        reasons.append(f"Concrete category: {category}")

    if LOW_SIGNAL_MARKET_MOVE.search(text):
        score -= 18
        reasons.append("Market-move headline")

    if FRAMING_TERMS.search(text):
        score -= 14
        reasons.append("Framing/explainer language")
    if MODAL_TERMS.search(text):
        score -= 4
        reasons.append("Hedging/modality language")

    if "opinion" in (source or "").lower():
        score -= 20
        reasons.append("Opinion source")

    score = max(0, min(100, score))
    return score, reasons

def load_json(path: Path, default: Any) -> Any:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default
    return default

def save_json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")

def load_url_first_seen() -> Dict[str, str]:
    return load_json(URL_AGE_FILE, {})

def save_url_first_seen(d: Dict[str, str]) -> None:
    save_json(URL_AGE_FILE, d)

def url_age_days(first_seen_iso: str) -> Optional[int]:
    if not first_seen_iso:
        return None
    try:
        dt = dateparser.parse(first_seen_iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - dt
        return max(0, int(delta.total_seconds() // 86400))
    except Exception:
        return None

def evergreen_badge(first_seen_iso: str) -> Tuple[bool, Optional[int]]:
    days = url_age_days(first_seen_iso)
    if days is None:
        return (False, None)
    return (days >= EVERGREEN_DAYS, days)

def build_schema(item: Dict[str, Any]) -> Dict[str, Any]:
    title = item["title"]
    summary = item["summary"]
    source = item["source"]

    score, bullets = score_item(title, summary, source)
    category = classify_category(title, summary)
    strength = signal_strength(score)
    horizon = time_horizon(category)

    # Conservative default action
    # Triage should not output "Act" (reserve that for the deep-dive analysis step)
    if strength == "High":
        action = "Prepare/Monitor"
    elif strength == "Medium":
        action = "Prepare/Monitor"
    else: 
        action = "No Action"

    requires_read = (strength == "High" and category not in ["Noise"])

    is_evergreen, age_days = evergreen_badge(item.get("url_first_seen_at", ""))

    return {
        "title": title,
        "url": item["link"],
        "source": "WSJ",
        "published_at": item["published_at"],
        "feed": item.get("feed", ""),
        "category": category,
        "signal_strength": strength,
        "time_horizon": horizon,
        "signal_bullets": bullets,
        "mechanism": f"{category} developments can affect prices, incentives, or risk.",
        "action": action,
        "confidence": confidence(score),
        "raw_score": score,
        "snippet": (summary[:280] if summary else ""),
        "new_since_last_run": bool(item.get("new_since_last_run", False)),
        "requires_read": requires_read,

        # evergreen resurfacing flag
        "url_first_seen_at": item.get("url_first_seen_at", ""),
        "url_age_days": age_days,
        "evergreen_resurfaced": bool(is_evergreen),
    }


# =========================
# HTML Template
# =========================

HTML_TEMPLATE = Template(r"""
<!doctype html>
<html>
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>WSJ Signal Dashboard</title>
<style>
  :root { --bg:#0b0c10; --panel:#161821; --chip:#222; --text:#eee; --muted:#aaa; --warn:#f5c542; --new:#8ef0a6; }
  body { font-family:-apple-system,system-ui; background:var(--bg); color:var(--text); margin:0; }
  .wrap { max-width:1100px; margin:24px auto; padding:0 16px; }
  .header { display:flex; justify-content:space-between; align-items:baseline; gap:12px; flex-wrap:wrap; }
  .meta { color:var(--muted); font-size:12px; }
  .controls { margin:14px 0 18px; display:grid; grid-template-columns:1.2fr .9fr .7fr .8fr .7fr; gap:10px; }
  input, select { width:100%; padding:10px 12px; border-radius:12px; border:1px solid #2a2d3a; background:#0f1118; color:var(--text); outline:none; }
  .card { background:var(--panel); border-radius:14px; padding:14px; margin-bottom:12px; border:1px solid #252839; }
  .chips { display:flex; flex-wrap:wrap; gap:8px; }
  .chip { display:inline-block; padding:5px 10px; border-radius:999px; font-size:11px; background:var(--chip); color:#ddd; border:1px solid #2b2e3c; }
  .chip.warn { border-color:rgba(245,197,66,.55); color:var(--warn); }
  .chip.new { border-color:rgba(142,240,166,.55); color:var(--new); }
  .title { margin-top:10px; font-size:15px; font-weight:650; }
  .title a { color:#fff; text-decoration:none; }
  .title a:hover { text-decoration:underline; }
  .details { margin-top:10px; font-size:13px; color:#ddd; }
  details { margin-top:10px; }
  summary { cursor:pointer; color:#bbb; }
  .empty { padding:16px; border:1px dashed #2a2d3a; border-radius:14px; color:var(--muted); }
  .themes { margin-top:10px; color:var(--muted); font-size:12px; }
  .themes code { color:#cbd; }
</style>
</head>
<body>
<div class="wrap">
  <div class="header">
    <div>
      <h2 style="margin:0">WSJ Signal Dashboard</h2>
      <div class="meta">Generated {{ generated }} • Window: last {{ recent_hours }} hours (RSS published)</div>
      {% if themes_summary %}
      <div class="themes">Active themes loaded: <code>{{ themes_summary }}</code></div>
      {% endif %}
    </div>
  </div>

  <div class="controls">
    <input id="q" placeholder="Search title…" />
    <select id="feed"><option value="">All feeds</option></select>
    <select id="sig"><option value="">All signal</option><option>High</option><option>Medium</option><option>Low</option></select>
    <select id="hzn"><option value="">All horizons</option><option>Immediate</option><option>Medium</option><option>Structural</option></select>
    <select id="new"><option value="">New: all</option><option value="only">Only new</option><option value="no">Hide new</option></select>
  </div>

  <div id="cards"></div>
</div>

<script>
const DATA = {{ data | safe }};
const ANALYZE_BASE = {{ analyze_base_json | safe }};
const root = document.getElementById("cards");

const els = {
  q: document.getElementById("q"),
  feed: document.getElementById("feed"),
  sig: document.getElementById("sig"),
  hzn: document.getElementById("hzn"),
  newf: document.getElementById("new"),
};

function uniq(arr) { return Array.from(new Set(arr.filter(Boolean))).sort(); }

uniq(DATA.map(x => x.feed)).forEach(f => {
  const opt = document.createElement("option");
  opt.value = f; opt.textContent = f;
  els.feed.appendChild(opt);
});

function render() {
  const q = (els.q.value || "").toLowerCase().trim();
  const feed = els.feed.value;
  const sig = els.sig.value;
  const hzn = els.hzn.value;
  const newf = els.newf.value;

  let xs = DATA.slice();

  if (q) xs = xs.filter(x => (x.title || "").toLowerCase().includes(q));
  if (feed) xs = xs.filter(x => x.feed === feed);
  if (sig) xs = xs.filter(x => x.signal_strength === sig);
  if (hzn) xs = xs.filter(x => x.time_horizon === hzn);

  if (newf === "only") xs = xs.filter(x => x.new_since_last_run);
  if (newf === "no") xs = xs.filter(x => !x.new_since_last_run);

  xs.sort((a,b) => (b.raw_score || 0) - (a.raw_score || 0));

  root.innerHTML = "";
  if (!xs.length) {
    const d = document.createElement("div");
    d.className = "empty";
    d.textContent = "No items match your filters.";
    root.appendChild(d);
    return;
  }

  for (const x of xs) {
    const d = document.createElement("div");
    d.className = "card";

    const evergreenChip = x.evergreen_resurfaced
      ? `<span class="chip warn">Evergreen • first seen ${x.url_age_days}d ago</span>`
      : "";

    const newChip = x.new_since_last_run ? `<span class="chip new">NEW</span>` : "";

    const analyzeHref = `http://127.0.0.1:5050/analyze?u=${encodeURIComponent(x.url || "")}&t=${encodeURIComponent(x.title || "")}`;



    d.innerHTML = `
      <div class="chips">
        <span class="chip">${x.feed || "WSJ"}</span>
        <span class="chip">${x.category}</span>
        <span class="chip">${x.signal_strength}</span>
        <span class="chip">${x.action}</span>
        <span class="chip">Conf ${x.confidence}/5</span>
        ${newChip}
        ${evergreenChip}
      </div>

      <div class="title">
        <a href="${x.url}" target="_blank" rel="noopener">${x.title}</a>
        <span style="color:#777"> • </span>
        <a href="${analyzeHref}"
	    target="_self"
	    onclick="event.stopPropagation();"
	    style="color:#9ad; font-weight:650; text-decoration:none">
	  Analyze
	</a>
      </div>

      <div class="meta">RSS published: ${x.published_at || ""} • ${x.time_horizon}</div>

      <div class="details">${x.mechanism || ""}</div>

      <details>
        <summary>Details</summary>
        <div class="details"><strong>Signal bullets</strong></div>
        <ul>${(x.signal_bullets || []).map(b => `<li>${b}</li>`).join("")}</ul>
        <div class="details"><strong>Snippet</strong></div>
        <div class="details">${x.snippet || "—"}</div>
      </details>
    `;
    root.appendChild(d);
  }
}

["input","change"].forEach(evt => {
  els.q.addEventListener(evt, render);
  els.feed.addEventListener(evt, render);
  els.sig.addEventListener(evt, render);
  els.hzn.addEventListener(evt, render);
  els.newf.addEventListener(evt, render);
});

render();
</script>
</body>
</html>
""")


# =========================
# Main
# =========================

def main() -> None:
    # Ensure directories exist
    (BASE_DIR / "data").mkdir(parents=True, exist_ok=True)
    (BASE_DIR / "output").mkdir(parents=True, exist_ok=True)

    # Load run state
    run_state = load_json(RUN_STATE_FILE, {"last_run_at": "", "last_run_urls": []})
    last_run_urls = set(run_state.get("last_run_urls", []) or [])

    url_first_seen = load_url_first_seen()
    now_iso = utc_now_iso()

    items: List[Dict[str, Any]] = []
    total_seen_new = 0
    total_recent = 0

    for url in FEEDS:
        feed = feedparser.parse(url)
        feed_title = feed.feed.get("title", "WSJ RSS")

        for e in feed.entries[:200]:
            title = (e.get("title") or "").strip()
            link = (e.get("link") or "").strip()
            summary = strip_html(e.get("summary", ""))
            published_at = parse_rss_published_iso(e)

            if not title or not link:
                continue

            # evergreen memory (not gating)
            if link not in url_first_seen:
                url_first_seen[link] = now_iso
                total_seen_new += 1

            # 48h gating by RSS published
            cat_guess = classify_category(title, summary)
            if not is_recent(published_at, hours=window_hours_for_category(cat_guess)):
                continue

            total_recent += 1

            items.append({
                "title": title,
                "link": link,
                "summary": summary,
                "published_at": published_at,
                "source": feed_title,
                "feed": feed_title,
                "url_first_seen_at": url_first_seen.get(link, ""),
                "new_since_last_run": (link not in last_run_urls),
            })

    save_url_first_seen(url_first_seen)

    # Deduplicate by URL across feeds
    by_url: Dict[str, Dict[str, Any]] = {}
    for it in items:
        by_url[it["link"]] = it
    items = list(by_url.values())

    # Persist run state for next diff
    save_json(RUN_STATE_FILE, {
        "last_run_at": now_iso,
        "last_run_urls": [it["link"] for it in items],
    })

    schema_items = [build_schema(i) for i in items]

    # TODO: analyze_base / ANALYZE_BASE is dead code. The template hardcodes the Flask
    # route (http://127.0.0.1:5050/analyze) instead of using this file:// URI.
    # Safe to remove in a future cleanup pass.
    analyze_base = (BASE_DIR / "templates" / "analyze.html").resolve().as_uri()

    themes_summary = ""
    themes_obj = load_json(THEMES_FILE, {})
    if isinstance(themes_obj, dict) and "active_themes" in themes_obj:
        try:
            themes_summary = ", ".join([t.get("name", "") for t in themes_obj.get("active_themes", []) if t.get("name")])[:160]
        except Exception:
            themes_summary = ""

    html = HTML_TEMPLATE.render(
        generated=datetime.now().strftime("%Y-%m-%d %H:%M"),
        recent_hours=RECENT_HOURS,
        data=json.dumps(schema_items, ensure_ascii=False),
        analyze_base_json=json.dumps(analyze_base),
        themes_summary=themes_summary,
    )

    out = BASE_DIR / "output" / "triage.html"
    out.write_text(html, encoding="utf-8")

    print(f"New URLs added to evergreen store this run: {total_seen_new}")
    print(f"Items passing {RECENT_HOURS}h RSS cutoff (pre-dedupe): {total_recent}")
    print(f"Items on dashboard (deduped): {len(items)}")
    print(f"Wrote {out.resolve()}")


if __name__ == "__main__":
    main()
