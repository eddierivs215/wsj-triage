#!/bin/bash
# Migration script: reorganizes flat structure into organized directories
# Review before running. Idempotent (safe to run multiple times).

set -e
cd "$(dirname "$0")"

echo "Migrating wsj-triage to new structure..."

# Move source files
[ -f wsj_triage.py ] && mv wsj_triage.py src/triage.py && echo "  wsj_triage.py → src/triage.py"
[ -f weekly_synthesis.py ] && mv weekly_synthesis.py src/synthesis.py && echo "  weekly_synthesis.py → src/synthesis.py"
[ -f server.py ] && mv server.py src/server.py && echo "  server.py → src/server.py"

# Move templates
[ -f analyze.html ] && mv analyze.html templates/analyze.html && echo "  analyze.html → templates/analyze.html"

# Move config
[ -f themes.json ] && mv themes.json config/themes.json && echo "  themes.json → config/themes.json"

# Move data files
[ -f analysis_log.jsonl ] && mv analysis_log.jsonl data/analysis_log.jsonl && echo "  analysis_log.jsonl → data/analysis_log.jsonl"
[ -f url_first_seen.json ] && mv url_first_seen.json data/url_first_seen.json && echo "  url_first_seen.json → data/url_first_seen.json"
[ -f run_state.json ] && mv run_state.json data/run_state.json && echo "  run_state.json → data/run_state.json"

# Move generated output
[ -f wsj_triage.html ] && mv wsj_triage.html output/triage.html && echo "  wsj_triage.html → output/triage.html"
[ -f weekly_memo.md ] && mv weekly_memo.md output/weekly_memo.md && echo "  weekly_memo.md → output/weekly_memo.md"
[ -f weekly_memo.html ] && mv weekly_memo.html output/weekly_memo.html && echo "  weekly_memo.html → output/weekly_memo.html"

# Remove redundant files
[ -f seen_urls.json ] && rm seen_urls.json && echo "  Removed seen_urls.json (redundant)"

echo "Migration complete."
echo ""
echo "Next: Update file paths in src/*.py to reflect new structure."
