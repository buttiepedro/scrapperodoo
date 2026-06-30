"""Scraping de la página de servicios."""

from .fetch import get_soup
from .text import clean, strip_noise


def scrape_servicios() -> list[dict]:
    soup = get_soup("/servicios")
    strip_noise(soup)
    servicios = []
    seen = set()

    for h3 in soup.find_all("h3"):
        nombre = clean(h3.get_text())
        if not nombre or len(nombre) < 5 or nombre in seen:
            continue
        seen.add(nombre)
        desc_parts = []
        nxt = h3.find_next_sibling()
        while nxt and nxt.name not in ("h2", "h3"):
            if nxt.name == "p":
                t = clean(nxt.get_text())
                if t:
                    desc_parts.append(t)
            nxt = nxt.find_next_sibling()
        servicios.append({"nombre": nombre, "descripcion": " ".join(desc_parts)})

    return servicios
