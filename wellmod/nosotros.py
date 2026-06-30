"""Scraping de la página "Nosotros" (descripción, historia y fundadores)."""

import re

from bs4 import BeautifulSoup

from .fetch import get_soup
from .text import clean, get_lines, strip_noise


def _scrape_historia_timeline(soup: BeautifulSoup) -> list[dict]:
    """
    Extrae la línea de tiempo (sección s_timeline) capturando, por cada hito,
    el año, el título y el párrafo descriptivo de la tarjeta.

    Estructura del HTML (Odoo snippet s_timeline):
        div.s_timeline_row
          ├── div.s_timeline_date  → <b>2017</b>
          └── div.card-body
                ├── h5.card-title   → "Inicio"
                └── p.card-text     → "El arquitecto Marcelo Palmero ..."
    """
    historia = []

    for row in soup.select("div.s_timeline_row"):
        date_el = row.select_one(".s_timeline_date")
        año = clean(date_el.get_text()) if date_el else ""
        if not re.fullmatch(r"(19|20)\d{2}", año):
            continue

        title_el = row.select_one(".card-title") or row.find(["h2", "h3", "h4", "h5", "h6"])
        hito = clean(title_el.get_text()) if title_el else ""

        body = row.select_one(".card-body")
        if body is not None:
            parrafos = [clean(p.get_text()) for p in body.find_all("p")]
        else:
            parrafos = []
        descripcion = " ".join(p for p in parrafos if p)

        if not hito and not descripcion:
            continue

        historia.append({"año": año, "hito": hito, "descripcion": descripcion})

    return historia


def scrape_nosotros() -> dict:
    soup = get_soup("/about-us")
    strip_noise(soup)
    lines = get_lines(soup)

    historia = _scrape_historia_timeline(soup)

    if not historia:
        # Fallback: estructura del timeline no encontrada, usar texto lineal
        year_re = re.compile(r"^\d{4}$")
        i = 0
        while i < len(lines):
            if year_re.match(lines[i]) and i + 1 < len(lines):
                año = lines[i]
                hito = lines[i + 1]
                if not historia or historia[-1]["año"] != año or historia[-1]["hito"] != hito:
                    historia.append({"año": año, "hito": hito, "descripcion": ""})
                i += 2
            else:
                i += 1

    fundadores = []
    seen = set()
    for h4 in soup.find_all("h4"):
        nombre = clean(h4.get_text())
        if nombre.startswith(("Arq.", "Ing.")) and nombre not in seen:
            seen.add(nombre)
            testimonio_parts = []
            nxt = h4.find_next_sibling()
            while nxt and nxt.name not in ("h4", "h3", "h2"):
                if nxt.name == "p":
                    t = clean(nxt.get_text())
                    if t:
                        testimonio_parts.append(t)
                nxt = nxt.find_next_sibling()
            fundadores.append({"nombre": nombre, "testimonio": " ".join(testimonio_parts)})

    descripcion = ""
    for p in soup.find_all("p"):
        t = clean(p.get_text())
        if "WellMod Argentina" in t and len(t) > 100:
            descripcion = t
            break

    return {"descripcion": descripcion, "historia": historia, "fundadores": fundadores}
