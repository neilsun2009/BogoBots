#!/bin/bash
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-/app/BogoBots}"
CRON_SCRIPT="${AI_NEWS_CRON_SCRIPT:-${PROJECT_DIR}/scripts/ai_news_cron.sh}"
PYTHON_BIN="${PYTHON_BIN:-/usr/local/bin/python3}"
LOG_DIR="${PROJECT_DIR}/logs"
CRON_LOG="${LOG_DIR}/ai_news_cron.cron.log"

mkdir -p "$LOG_DIR"
chmod +x "$CRON_SCRIPT"

# Same 5-minute cadence the crawl script expects (queue + lock).
CRON_LINE="*/5 * * * * cd /app/BogoBots && TZ=Asia/Shanghai PYTHON_BIN=${PYTHON_BIN} ${CRON_SCRIPT} >> ${CRON_LOG} 2>&1"

{
  crontab -l 2>/dev/null | grep -v -- 'ai_news_cron.sh' || true
  echo "MAILTO=\"\""
  echo "$CRON_LINE"
} | crontab -

echo "Registered cron job:"
crontab -l
