#!/bin/bash
set -euo pipefail

if [ -x /app/BogoBots/scripts/register_ai_news_cron.sh ]; then
  /app/BogoBots/scripts/register_ai_news_cron.sh
else
  register-ai-news-cron
fi
cron
exec "$@"
