#!/bin/bash

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"      # .../BogoBots/BogoBots
REPO_ROOT="$(cd "$PROJECT_DIR/.." && pwd)"           # .../BogoBots

cd "$PROJECT_DIR" || exit 1

LOG_DIR="$PROJECT_DIR/logs"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
LOG_FILE="$LOG_DIR/ai_hub_crawl_${TIMESTAMP}.log"
mkdir -p "$LOG_DIR"

# Keep cwd at project dir (so streamlit secrets are picked up),
# but import package from repo root and avoid cwd module shadowing.
PYTHONPATH="$REPO_ROOT" python -u -P -m BogoBots.crawlers.scripts.run_news_crawl --summarize --days 1 2>&1 | tee -a "$LOG_FILE"