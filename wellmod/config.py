"""Configuración y constantes del scraper de wellmod.odoo.com."""

import os

BASE_URL = "https://wellmod.odoo.com"
OUTPUT_FILE = os.getenv("WELLMOD_OUTPUT_FILE", "wellmod_knowledge_base.json")
DELAY = float(os.getenv("WELLMOD_REQUEST_DELAY", "1.5"))  # segundos entre requests

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# URLs estáticas de tipologías como fallback si el scraping del catálogo falla
TIPOLOGIAS_FALLBACK = [
    "/en/w20-suite",
    "/en/w26-suite",
    "/en/w30-2",
    "/en/w30-1",
    "/en/w40",
    "/en/w52",
    "/en/w60",
    "/en/w63",
    "/en/w66",
    "/en/w80",
    "/en/w-oficinas",
]

OBRAS_CATALOG = [
    {"slug": "viviendas", "path": "/obras-viviendas", "nombre": "Viviendas"},
    {"slug": "turismo", "path": "/obras-turismo", "nombre": "Turismo"},
    {"slug": "oficinas", "path": "/obras-oficinas", "nombre": "Oficinas"},
    {"slug": "oil-and-gas", "path": "/obras-oilandgas", "nombre": "Oil and Gas"},
]
