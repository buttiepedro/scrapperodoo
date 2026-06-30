"""Scraping de la página de inicio (descripción, pilares y estadísticas)."""

import re

from .fetch import get_soup
from .text import clean, get_lines, strip_noise


def scrape_home() -> dict:
    soup = get_soup("/")
    strip_noise(soup)
    lines = get_lines(soup)

    PILARES_NOMBRES = {"MODULAR", "TRANSPORTABLE", "INMEDIATO", "SIMPLE", "SUSTENTABLE"}
    pilares = []
    estadisticas = {}

    for h3 in soup.find_all("h3"):
        nombre = clean(h3.get_text()).upper()
        if nombre in PILARES_NOMBRES:
            desc_parts = []
            nxt = h3.find_next_sibling()
            while nxt and nxt.name not in ("h2", "h3", "h4", "h5"):
                if nxt.name == "p":
                    t = clean(nxt.get_text())
                    if t:
                        desc_parts.append(t)
                nxt = nxt.find_next_sibling()
            pilares.append({"nombre": nombre, "descripcion": " ".join(desc_parts)})

    full_text = "\n".join(lines)
    for pattern, label in [
        (r"(\d+)\s*AÑOS", "años_trayectoria"),
        (r"([\d.,]+)\s*m²?\s*CONSTRUIDOS", "m2_construidos"),
        (r"(\d+)\s*MÓDULOS", "modulos_producidos"),
        (r"(\d+)\s*HISTORIAS", "historias_de_exito"),
    ]:
        m = re.search(pattern, full_text, re.I)
        if m:
            estadisticas[label] = m.group(1)

    descripcion = ""
    KEYWORDS = ("modular transportable", "arquitectura modular", "preconstruid", "residencial, comercial")
    for p in soup.find_all("p"):
        t = clean(p.get_text())
        if any(kw in t.lower() for kw in KEYWORDS) and 60 < len(t) < 600:
            descripcion = t
            break

    if not descripcion:
        for p in soup.find_all("p"):
            t = clean(p.get_text())
            if len(t) > 80 and "copyright" not in t.lower() and "odoo" not in t.lower():
                descripcion = t
                break

    return {"descripcion": descripcion, "pilares": pilares, "estadisticas": estadisticas}
