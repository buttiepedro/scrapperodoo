"""Orquestación: ejecuta cada sección, arma el JSON final y lo guarda en disco."""

import json
from datetime import datetime

import requests

from .config import (
    BASE_URL,
    HEADERS,
    KNOWLEDGE_IMPORT_TIMEOUT,
    KNOWLEDGE_IMPORT_TOKEN,
    KNOWLEDGE_IMPORT_URL,
    OUTPUT_FILE,
)
from .faqs import scrape_faqs
from .home import scrape_home
from .nosotros import scrape_nosotros
from .obras import scrape_obras_catalog
from .servicios import scrape_servicios
from .tipologias import scrape_tipologia_detail, scrape_tipologias_catalog


def _safe(label: str, fn, default):
    """Ejecuta una sección del scraper; si falla, registra el error y sigue.

    Evita que el fallo de una sola página (p.ej. un 404) tire toda la corrida
    y deje el JSON sin generar.
    """
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001 - robustez: una sección no debe tumbar el resto
        print(f"  ⚠ Falló la sección '{label}': {exc}")
        return default


def _send_knowledge_base(path: str) -> None:
    with open(path, "rb") as f:
        resp = requests.post(
            KNOWLEDGE_IMPORT_URL,
            headers={
                "User-Agent": HEADERS["User-Agent"],
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": HEADERS["Accept-Language"],
                "X-Knowledge-Token": KNOWLEDGE_IMPORT_TOKEN,
                "Content-Type": "application/json",
            },
            data=f,
            timeout=KNOWLEDGE_IMPORT_TIMEOUT,
        )

    if resp.status_code >= 400:
        raise RuntimeError(
            "Error al importar conocimiento "
            f"(status={resp.status_code}): {resp.text[:500]}"
        )

    print(
        "  ✓ JSON enviado a knowledge/import "
        f"(status={resp.status_code})"
    )


def run() -> None:
    print("=" * 60)
    print("  Wellmod Scraper")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    output = {
        "metadata": {
            "scraped_at": datetime.now().isoformat(),
            "source": BASE_URL,
            "version": "1.0",
        }
    }

    print("\n[1/6] Home →")
    output["empresa"] = _safe(
        "empresa", scrape_home, {"descripcion": "", "pilares": [], "estadisticas": {}}
    )

    print("\n[2/6] Nosotros →")
    output["nosotros"] = _safe(
        "nosotros", scrape_nosotros, {"descripcion": "", "historia": [], "fundadores": []}
    )

    print("\n[3/6] Servicios →")
    output["servicios"] = _safe("servicios", scrape_servicios, [])

    print("\n[4/6] FAQs →")
    output["faqs"] = _safe("faqs", scrape_faqs, [])

    print("\n[5/6] Tipologías →")
    tipologia_urls = _safe("tipologias-catalogo", scrape_tipologias_catalog, [])
    print(f"  → {len(tipologia_urls)} productos encontrados")

    tipologias = []
    for url in tipologia_urls:
        detail = _safe(f"tipologia {url}", lambda u=url: scrape_tipologia_detail(u), None)
        if detail is None:
            continue
        tipologias.append(detail)
        print(f"  ✓ {detail['nombre'] or url}")

    output["tipologias"] = tipologias

    print("\n[6/6] Obras →")
    obras = _safe("obras", scrape_obras_catalog, [])
    output["obras"] = obras

    output["contacto"] = {
        "whatsapp_numero": "+54 9 351 816-0094",
        "whatsapp_url": "https://wa.me/5493518160094",
        "web": BASE_URL,
        "mensaje_sugerido_tipologias": (
            "¡Hola! Me gustaría recibir información sobre "
            "las distintas tipologías Wellmod. ¡Gracias!"
        ),
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # El envío al CRM no debe tumbar la corrida: el JSON ya está guardado y el
    # entrypoint corre con `set -e` (un error acá impediría arrancar la API).
    print("  → Enviando JSON a CRM...")
    _safe("envío al CRM", lambda: _send_knowledge_base(OUTPUT_FILE), None)

    print(f"\n{'=' * 60}")
    print(f"  ✓ JSON guardado en: {OUTPUT_FILE}")
    print(f"  Tipologías: {len(tipologias)}")
    print(f"  Obras:      {sum(len(cat['proyectos']) for cat in obras)}")
    print(f"  Servicios:  {len(output['servicios'])}")
    print(f"  FAQs:       {len(output['faqs'])}")
    print(f"  Hitos hist: {len(output['nosotros']['historia'])}")
    print("=" * 60)
