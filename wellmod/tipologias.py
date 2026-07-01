"""Scraping de tipologías: catálogo de modelos y ficha de detalle de cada uno."""

import re

import requests

from .config import BASE_URL, TIPOLOGIAS_FALLBACK
from .fetch import get_soup
from .text import clean, extract_price, extract_whatsapp, get_lines, strip_noise


def scrape_tipologias_catalog() -> list[str]:
    """
    Extrae las URLs de detalle de cada tipología desde la página del catálogo.
    Retorna lista de paths relativos o URLs absolutas.
    """
    urls = []
    seen = set()

    try:
        soup = get_soup("/tipologias")
    except requests.RequestException as exc:
        print(f"  ⚠ No se pudo abrir el catálogo (/tipologias): {exc}. Usando URLs estáticas de fallback.")
        soup = None

    if soup is not None:
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/en/w" in href and href not in seen:
                seen.add(href)
                urls.append(href if href.startswith("http") else BASE_URL + href)

    if not urls:
        print("  ⚠ No se encontraron links dinámicamente. Usando URLs estáticas de fallback.")
        urls = [BASE_URL + p for p in TIPOLOGIAS_FALLBACK]

    return urls


def scrape_tipologia_detail(url: str) -> dict:
    soup = get_soup(url)
    strip_noise(soup)
    lines = get_lines(soup)
    full_text = "\n".join(lines)

    result = {
        "url": url,
        "link": url,  # link accesible para compartir con el usuario
        "nombre": "",
        "descripcion": "",
        "precio": "",
        "precio_nota": "Valor puesto en fábrica (Córdoba). Traslado y montaje se cotiza por separado.",
        "whatsapp_consulta": extract_whatsapp(soup),
        "incluye": [],
        "exclusiones": [],
        "opcionales": [],
        "opcionales_premium": [],
    }

    for tag in soup.find_all(re.compile(r"^h[12]$")):
        t = clean(tag.get_text())
        if t and len(t) < 80 and "wellmod" not in t.lower() and "tipolog" not in t.lower():
            result["nombre"] = t
            break

    result["precio"] = extract_price(full_text)

    for p in soup.find_all("p"):
        t = clean(p.get_text())
        if (
            len(t) > 50
            and "U$D" not in t
            and "derechos reservados" not in t.lower()
            and "Odoo" not in t
            and "cookie" not in t.lower()
        ):
            result["descripcion"] = t
            break

    SECTION_PATTERNS = [
        (re.compile(r"^opcionales?\s*premium", re.I), "opcionales_premium"),
        (re.compile(r"^opcionales?", re.I), "opcionales"),
        (re.compile(r"^exclusiones?", re.I), "exclusiones"),
        (re.compile(r"^incluye", re.I), "incluye"),
    ]

    STOP_WORDS = {"anterior", "siguiente", "antersiguiente", "copyright"}

    current_section = None
    section_buffer: dict[str, list[str]] = {
        "incluye": [],
        "exclusiones": [],
        "opcionales": [],
        "opcionales_premium": [],
    }

    for line in lines:
        if line.lower() in STOP_WORDS:
            break

        line_stripped = line.rstrip(":").strip()
        matched_section = None
        for pattern, key in SECTION_PATTERNS:
            if pattern.match(line_stripped):
                matched_section = key
                break

        if matched_section:
            current_section = matched_section
            continue

        if current_section and current_section in section_buffer:
            section_buffer[current_section].append(line)

    BULLET_RE = re.compile(r"[•ò●]")

    def parse_bullet_items(raw_lines: list[str]) -> list[str]:
        combined = " ".join(raw_lines)
        parts = BULLET_RE.split(combined)
        items = []
        for part in parts:
            cleaned = clean(part)
            if cleaned and len(cleaned) > 2:
                items.append(cleaned)
        return items

    for key in ("incluye", "exclusiones", "opcionales", "opcionales_premium"):
        result[key] = parse_bullet_items(section_buffer[key])

    return result
