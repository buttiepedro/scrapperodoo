"""Scraping de la página de preguntas frecuentes (FAQs)."""

import re

from bs4 import BeautifulSoup

from .fetch import get_soup
from .text import clean, get_lines, strip_noise


def scrape_faqs() -> list[dict]:
    soup = get_soup("/faqs")
    strip_noise(soup)

    faqs = _scrape_faqs_accordion(soup)
    if faqs:
        return faqs

    # Fallback: estructura de acordeón no encontrada, usar texto lineal
    return _scrape_faqs_lines(soup)


def _scrape_faqs_accordion(soup: BeautifulSoup) -> list[dict]:
    """Extrae las FAQs del acordeón de Odoo.

    Cada categoría es un ``div.accordion`` precedido por un ``span.h4-fs`` con su
    título; dentro, cada ``div.card`` tiene la pregunta en ``.card-header`` y la
    respuesta en ``.card-body``. Esto evita arrastrar el intro/footer de la
    página (p.ej. "¿Tienes alguna duda?") y empareja bien pregunta y respuesta.
    """
    faqs = []

    for acc in soup.select("div.accordion"):
        # Categoría: título (span.h4-fs) más cercano antes del acordeón.
        categoria = "GENERAL"
        for el in acc.find_all_previous("span", class_="h4-fs"):
            titulo = clean(el.get_text()).upper()
            if titulo:
                categoria = titulo
                break

        for card in acc.select("div.card"):
            head = card.select_one(".card-header")
            pregunta = clean(head.get_text()) if head else ""
            if not pregunta:
                continue

            body = card.select_one(".card-body")
            if body is not None:
                parrafos = [clean(p.get_text()) for p in body.find_all("p")]
                respuesta = " ".join(p for p in parrafos if p) or clean(body.get_text())
            else:
                respuesta = ""

            faqs.append({
                "categoria": categoria,
                "pregunta": pregunta,
                "respuesta": respuesta,
            })

    return faqs


def _scrape_faqs_lines(soup: BeautifulSoup) -> list[dict]:
    """Fallback histórico: detecta preguntas (``¿...?``) en el texto lineal."""
    lines = get_lines(soup)

    CATEGORIAS = {"CONSTRUCTIVO", "TRASLADO Y MONTAJE", "FINANCIACIÓN", "OTRAS PREGUNTAS"}
    faqs = []
    current_cat = "GENERAL"

    i = 0
    while i < len(lines):
        line = lines[i]

        if line.upper() in CATEGORIAS:
            current_cat = line.upper()
            i += 1
            continue

        preguntas = re.findall(r"¿[^¿?]+\?", line)
        if preguntas:
            respuesta = re.sub(r"¿[^¿?]+\?", "", line).strip()

            if not respuesta:
                j = i + 1
                while j < len(lines) and j < i + 8:
                    candidate = lines[j]
                    if not candidate.startswith("¿") and len(candidate) > 15:
                        respuesta = candidate
                        break
                    j += 1

            for pregunta in preguntas:
                faqs.append({
                    "categoria": current_cat,
                    "pregunta": clean(pregunta),
                    "respuesta": clean(respuesta),
                })

        i += 1

    return faqs
