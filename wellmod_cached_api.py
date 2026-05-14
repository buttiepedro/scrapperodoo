#!/usr/bin/env python3
"""
API cacheada para exponer wellmod_knowledge_base.json

Arquitectura (opcion 2):
- Un job diario actualiza el archivo JSON con wellmod_scraper.py
- Esta API solo entrega el ultimo JSON generado (rapida y estable)

Uso local:
  pip install -r requirements_api.txt
  uvicorn wellmod_cached_api:app --host 0.0.0.0 --port 8080
"""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("WELLMOD_DATA_DIR", str(BASE_DIR / "data")))
JSON_FILE = Path(os.getenv("WELLMOD_JSON_FILE", str(DATA_DIR / "wellmod_knowledge_base.json")))
SCRAPER_FILE = Path(os.getenv("WELLMOD_SCRAPER_FILE", str(BASE_DIR / "wellmod_scraper.py")))
REFRESH_TOKEN = os.getenv("WELLMOD_REFRESH_TOKEN", "")

app = FastAPI(title="Wellmod Cached API", version="1.0.0")


def _load_json() -> dict[str, Any]:
    if not JSON_FILE.exists():
        raise HTTPException(status_code=404, detail="JSON cache not found. Run scraper first.")

    try:
        with JSON_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"Invalid JSON cache: {exc}") from exc


@app.on_event("startup")
def ensure_data_dir() -> None:
    JSON_FILE.parent.mkdir(parents=True, exist_ok=True)


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "service": "wellmod-cached-api",
        "utc": datetime.now(timezone.utc).isoformat(),
        "json_exists": JSON_FILE.exists(),
    }


@app.get("/wellmod/knowledge-base")
def get_knowledge_base() -> JSONResponse:
    data = _load_json()
    return JSONResponse(content=data)


@app.get("/wellmod/metadata")
def get_metadata() -> dict[str, Any]:
    data = _load_json()
    metadata = data.get("metadata", {})
    obras = data.get("obras", [])
    return {
        "source": metadata.get("source"),
        "scraped_at": metadata.get("scraped_at"),
        "version": metadata.get("version"),
        "tipologias": len(data.get("tipologias", [])),
        "obras_categorias": len(obras),
        "obras": sum(len(cat.get("proyectos", [])) for cat in obras),
        "servicios": len(data.get("servicios", [])),
        "faqs": len(data.get("faqs", [])),
    }


@app.post("/wellmod/refresh")
def refresh_cache(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    """
    Endpoint opcional para refrescar cache manualmente.
    Requiere header: Authorization: Bearer <WELLMOD_REFRESH_TOKEN>
    """
    if not REFRESH_TOKEN:
        raise HTTPException(status_code=403, detail="Refresh token not configured")

    expected = f"Bearer {REFRESH_TOKEN}"
    if authorization != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")

    if not SCRAPER_FILE.exists():
        raise HTTPException(status_code=500, detail="Scraper file not found")

    try:
        result = subprocess.run(
            ["python", str(SCRAPER_FILE)],
            check=True,
            capture_output=True,
            text=True,
            timeout=600,
            cwd=str(BASE_DIR),
        )
    except subprocess.CalledProcessError as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Scraper failed",
                "stdout": exc.stdout[-2000:],
                "stderr": exc.stderr[-2000:],
            },
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(status_code=504, detail=f"Scraper timed out: {exc}") from exc

    data = _load_json()
    return {
        "ok": True,
        "scraped_at": data.get("metadata", {}).get("scraped_at"),
        "stdout_tail": result.stdout[-1200:],
    }
