#!/bin/sh
set -eu

: "${WELLMOD_API_HOST:=0.0.0.0}"
: "${WELLMOD_API_PORT:=8080}"
: "${RUN_SCRAPER_ON_START:=true}"
: "${AUTO_REFRESH_EVERY_HOURS:=24}"
: "${WELLMOD_OUTPUT_FILE:=/app/data/wellmod_knowledge_base.json}"
: "${WELLMOD_JSON_FILE:=/app/data/wellmod_knowledge_base.json}"

mkdir -p "$(dirname "$WELLMOD_OUTPUT_FILE")"

run_scraper() {
  echo "[entrypoint] Running scraper..."
  python /app/wellmod_scraper.py
  echo "[entrypoint] Scraper finished."
}

if [ "$RUN_SCRAPER_ON_START" = "true" ]; then
  run_scraper
fi

if [ "$AUTO_REFRESH_EVERY_HOURS" -gt 0 ]; then
  (
    while true; do
      sleep "$((AUTO_REFRESH_EVERY_HOURS * 3600))"
      run_scraper || echo "[entrypoint] Scheduled refresh failed."
    done
  ) &
fi

echo "[entrypoint] Starting API on ${WELLMOD_API_HOST}:${WELLMOD_API_PORT}"
exec uvicorn wellmod_cached_api:app --host "$WELLMOD_API_HOST" --port "$WELLMOD_API_PORT"
