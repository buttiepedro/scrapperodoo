#!/bin/sh
set -eu

: "${WELLMOD_API_HOST:=0.0.0.0}"
: "${WELLMOD_API_PORT:=8080}"
: "${RUN_SCRAPER_ON_START:=true}"
: "${AUTO_REFRESH_EVERY_HOURS:=24}"
: "${SERVE_API:=true}"
: "${WELLMOD_OUTPUT_FILE:=/app/data/wellmod_knowledge_base.json}"
: "${WELLMOD_JSON_FILE:=/app/data/wellmod_knowledge_base.json}"

mkdir -p "$(dirname "$WELLMOD_OUTPUT_FILE")"

run_scraper() {
  echo "[entrypoint] Running scraper..."
  python /app/wellmod_scraper.py
  echo "[entrypoint] Scraper finished."
}

refresh_loop() {
  while true; do
    sleep "$((AUTO_REFRESH_EVERY_HOURS * 3600))"
    run_scraper || echo "[entrypoint] Scheduled refresh failed."
  done
}

if [ "$RUN_SCRAPER_ON_START" = "true" ]; then
  run_scraper
fi

if [ "$SERVE_API" = "true" ]; then
  # API HTTP activada: refresh en segundo plano + servidor uvicorn en primer plano.
  if [ "$AUTO_REFRESH_EVERY_HOURS" -gt 0 ]; then
    refresh_loop &
  fi
  echo "[entrypoint] Starting API on ${WELLMOD_API_HOST}:${WELLMOD_API_PORT}"
  exec uvicorn wellmod_cached_api:app --host "$WELLMOD_API_HOST" --port "$WELLMOD_API_PORT"
else
  # API HTTP deshabilitada (SERVE_API=false): solo scraper -> envío al CRM.
  echo "[entrypoint] API HTTP deshabilitada (SERVE_API=false). Modo scraper -> CRM."
  if [ "$AUTO_REFRESH_EVERY_HOURS" -gt 0 ]; then
    # Primer plano: mantiene vivo el contenedor y refresca (y reenvía al CRM) cada N horas.
    refresh_loop
  else
    echo "[entrypoint] AUTO_REFRESH_EVERY_HOURS=0: corrida única, el contenedor finaliza."
  fi
fi
