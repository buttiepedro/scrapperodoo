#!/bin/sh
set -eu

: "${WELLMOD_API_HOST:=0.0.0.0}"
: "${WELLMOD_API_PORT:=8080}"
: "${RUN_SCRAPER_ON_START:=true}"
: "${DAILY_REFRESH_TIME:=00:00}"
: "${WELLMOD_OUTPUT_FILE:=/app/data/wellmod_knowledge_base.json}"
: "${WELLMOD_JSON_FILE:=/app/data/wellmod_knowledge_base.json}"

mkdir -p "$(dirname "$WELLMOD_OUTPUT_FILE")"

run_scraper() {
  echo "[entrypoint] Running scraper..."
  python /app/wellmod_scraper.py
  echo "[entrypoint] Scraper finished."
}

if [ "$RUN_SCRAPER_ON_START" = "true" ]; then
  run_scraper || echo "[entrypoint] Initial scrape failed; continuing with API startup."
fi

if [ -n "$DAILY_REFRESH_TIME" ]; then
  (
    while true; do
      now_epoch=$(date +%s)
      target_today=$(date -d "today $DAILY_REFRESH_TIME" +%s)
      if [ "$target_today" -le "$now_epoch" ]; then
        target_epoch=$(date -d "tomorrow $DAILY_REFRESH_TIME" +%s)
      else
        target_epoch="$target_today"
      fi
      sleep_seconds=$((target_epoch - now_epoch))
      echo "[entrypoint] Next scraper run scheduled at $(date -d "@$target_epoch") (in ${sleep_seconds}s)"
      sleep "$sleep_seconds"
      run_scraper || echo "[entrypoint] Scheduled refresh failed."
    done
  ) &
fi

echo "[entrypoint] Starting API on ${WELLMOD_API_HOST}:${WELLMOD_API_PORT}"
exec uvicorn wellmod_cached_api:app --host "$WELLMOD_API_HOST" --port "$WELLMOD_API_PORT"
