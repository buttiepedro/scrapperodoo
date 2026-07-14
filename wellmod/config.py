"""Configuración y constantes del scraper de wellmod.odoo.com."""

import os

BASE_URL = "https://wellmod.odoo.com"
OUTPUT_FILE = os.getenv("WELLMOD_OUTPUT_FILE", "wellmod_knowledge_base.json")
DELAY = float(os.getenv("WELLMOD_REQUEST_DELAY", "1.5"))  # segundos entre requests
# El CRM expone su backend bajo /api (la ruta sin ese prefijo cae en el frontend
# estático y devuelve 405).
KNOWLEDGE_IMPORT_URL = os.getenv(
    "WELLMOD_KNOWLEDGE_IMPORT_URL",
    "https://crm2-wellmod.plataformabit.com/api/knowledge/import",
)
KNOWLEDGE_IMPORT_TOKEN = os.getenv("WELLMOD_KNOWLEDGE_IMPORT_TOKEN", "bitautomatizacion")
KNOWLEDGE_IMPORT_TIMEOUT = float(os.getenv("WELLMOD_KNOWLEDGE_IMPORT_TIMEOUT", "30"))

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
    "/en/w30",
    "/en/w30-s",
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
