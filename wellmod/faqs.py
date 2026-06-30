"""Scraping de la página de preguntas frecuentes (FAQs)."""

import re

from .fetch import get_soup
from .text import clean, get_lines, strip_noise


def scrape_faqs() -> list[dict]:
    soup = get_soup("/faqs")
    strip_noise(soup)
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
