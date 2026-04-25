#!/bin/bash
set -u

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"      # .../BogoBots/BogoBots
REPO_ROOT="$(cd "$PROJECT_DIR/.." && pwd)"           # .../BogoBots
PYTHON_BIN="${PYTHON_BIN:-/home/$(whoami)/miniconda3/envs/bogo/bin/python}"

cd "$PROJECT_DIR" || exit 1

LOG_DIR="$PROJECT_DIR/logs"
STATE_DIR="$PROJECT_DIR/logs/.ai_news_cron_state"
mkdir -p "$LOG_DIR" "$STATE_DIR"

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
LOG_FILE="$LOG_DIR/ai_hub_crawl_${TIMESTAMP}.log"
QUEUE_FILE="$STATE_DIR/source_queue.txt"
LOCK_FILE="$STATE_DIR/ai_news_cron.lock"
WINDOW_FILE="$STATE_DIR/window_key.txt"

# Process N sources each 5-min tick (default: 1 for low memory pressure)
MAX_SOURCES_PER_RUN="${MAX_SOURCES_PER_RUN:-20}"

# Keep cwd at project dir (so streamlit secrets are picked up),
# but import package from repo root and avoid cwd module shadowing.
export PYTHONPATH="$REPO_ROOT"
export MALLOC_ARENA_MAX="${MALLOC_ARENA_MAX:-2}"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"
export OPENBLAS_NUM_THREADS="${OPENBLAS_NUM_THREADS:-1}"

# Avoid overlapping runs from cron.
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  echo "[LOCK] another ai_news_cron.sh run is active, skip." | tee -a "$LOG_FILE"
  exit 0
fi

hour_now="$(date +%H)"
date_key="$(date +%Y%m%d)"
if [ "$hour_now" -lt 12 ]; then
  window_slot="00"
else
  window_slot="12"
fi
current_window="${date_key}_${window_slot}"

previous_window=""
if [ -f "$WINDOW_FILE" ]; then
  previous_window="$(cat "$WINDOW_FILE")"
fi

rebuild_queue() {
  echo "[QUEUE] rebuilding source queue for window ${current_window}" | tee -a "$LOG_FILE"
  "$PYTHON_BIN" -P - <<'PY' > "$QUEUE_FILE"
from BogoBots.services.news_source_service import NewsSourceService
sources = sorted(NewsSourceService.get_active_sources(), key=lambda s: s.id)
for s in sources:
    print(s.id)
PY
  echo "$current_window" > "$WINDOW_FILE"
}

# Reset from start every 12-hour window (00:00 and 12:00).
if [ "$previous_window" != "$current_window" ]; then
  rebuild_queue
fi

# If queue is missing/empty (all done), keep it empty and wait for next 12h reset.
if [ ! -s "$QUEUE_FILE" ]; then
  echo "[QUEUE] all sources completed for window ${current_window}; waiting for next reset at 00:00/12:00." | tee -a "$LOG_FILE"
  exit 0
fi

processed=0
while [ "$processed" -lt "$MAX_SOURCES_PER_RUN" ] && [ -s "$QUEUE_FILE" ]; do
  source_id="$(head -n 1 "$QUEUE_FILE" | tr -d '[:space:]')"
  if [ -z "$source_id" ]; then
    # drop empty line and continue
    sed -i '1d' "$QUEUE_FILE"
    continue
  fi
  if ! [[ "$source_id" =~ ^[0-9]+$ ]]; then
    echo "[QUEUE] invalid source id '${source_id}', dropping and continuing." | tee -a "$LOG_FILE"
    sed -i '1d' "$QUEUE_FILE"
    continue
  fi

  echo "[RUN] source_id=${source_id} window=${current_window}" | tee -a "$LOG_FILE"
  "$PYTHON_BIN" -u -P -m BogoBots.crawlers.scripts.run_news_crawl \
    --source-id "$source_id" \
    --days 1 \
    --summarize \
    2>&1 | tee -a "$LOG_FILE"
  rc=${PIPESTATUS[0]}

  if [ "$rc" -eq 0 ]; then
    # Remove processed source only on success.
    sed -i '1d' "$QUEUE_FILE"
    processed=$((processed + 1))
    echo "[DONE] source_id=${source_id} completed; removed from queue." | tee -a "$LOG_FILE"
  else
    echo "[RETRY] source_id=${source_id} failed rc=${rc}; will retry in next 5-min tick." | tee -a "$LOG_FILE"
    break
  fi
done

remaining="$(wc -l < "$QUEUE_FILE" | tr -d '[:space:]')"
echo "[STATUS] processed=${processed}, remaining=${remaining}, window=${current_window}" | tee -a "$LOG_FILE"