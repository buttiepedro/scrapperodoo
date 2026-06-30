"""Scraping de obras/proyectos realizados (catálogo por categoría + detalle)."""

import re

import requests

from .config import BASE_URL, OBRAS_CATALOG
from .fetch import get_soup
from .text import (
    clean,
    extract_project_metrics,
    find_card_container,
    get_lines,
    looks_like_location,
    strip_noise,
)


# Forma completa de un proyecto, para mantener las mismas claves aunque no haya
# ficha (404 o "PRÓXIMAMENTE"). Los datos de la tarjeta se superponen encima.
_EMPTY_OBRA = {
    "url": "",
    "nombre": "",
    "descripcion": "",
    "categoria": "",
    "ubicacion": "",
    "tamano": "",
    "anio": "",
}


def _is_project_link(href: str) -> bool:
    """True si el href apunta a una ficha de proyecto.

    Descarta anclas de navegación (``#top``), ``mailto:``/``tel:`` y enlaces al
    home. Las tarjetas marcadas "PRÓXIMAMENTE" solo tienen un ancla ``#top``: no
    hay que seguirlas (resolvían al home y ensuciaban la descripción).
    """
    href = (href or "").strip()
    if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
        return False
    path = href.split("#", 1)[0].rstrip("/")
    if path in ("", BASE_URL, BASE_URL.rstrip("/")):
        return False
    return True


def scrape_obra_detail(url: str) -> dict:
    soup = get_soup(url)
    strip_noise(soup)

    main = soup.find("main") or soup
    lines = get_lines(main)
    paragraphs = [clean(p.get_text()) for p in main.find_all("p") if clean(p.get_text())]

    result = {
        "url": url,
        "nombre": "",
        "descripcion": "",
        "categoria": "",
        "ubicacion": "",
        "tamano": "",
        "anio": "",
    }

    for tag in main.find_all(re.compile(r"^h[1-3]$")):
        t = clean(tag.get_text())
        if t and len(t) < 100 and "wellmod" not in t.lower():
            result["nombre"] = t.split(",")[0].strip()
            break

    if not result["nombre"] and lines:
        result["nombre"] = clean(lines[0]).split(",")[0].strip()

    for t in paragraphs:
        if len(t) > 50 and "copyright" not in t.lower() and "odoo" not in t.lower():
            result["descripcion"] = t
            break

    description_index = -1
    if result["descripcion"]:
        for idx, line in enumerate(lines):
            if result["descripcion"] in line:
                description_index = idx
                break

    search_lines = lines[description_index + 1 :] if description_index >= 0 else lines

    if not result["categoria"]:
        for line in search_lines:
            if line.lower() in {"vivienda", "viviendas", "turismo", "oficinas", "oil and gas"}:
                result["categoria"] = line
                break

    if not result["ubicacion"]:
        for line in search_lines:
            candidate = clean(line)
            if looks_like_location(candidate) and not re.fullmatch(r"\d{4}", candidate):
                if any(token in candidate.lower() for token in ("visita la galería", "visita la galeria", "descubr", "copyright", "odoo")):
                    continue
                if len(candidate) < 90:
                    result["ubicacion"] = candidate
                    break

    if not result["anio"]:
        for line in search_lines:
            m = re.fullmatch(r"(19|20)\d{2}", clean(line))
            if m:
                result["anio"] = clean(line)
                break

    if not result["tamano"]:
        for line in search_lines:
            m = re.search(r"\b\d+(?:[.,]\d+)?\s*m(?:²|2)\b", clean(line), re.I)
            if m:
                result["tamano"] = clean(m.group(0)).replace(" ", "")
                break

    metrics = extract_project_metrics(search_lines)
    for key, value in metrics.items():
        if not result[key] and value:
            result[key] = value

    return result


def scrape_obras_catalog() -> list[dict]:
    obras = []

    for category in OBRAS_CATALOG:
        print(f"  → {category['nombre']}")
        try:
            soup = get_soup(category["path"])
        except requests.RequestException as exc:
            # Una categoría caída (p.ej. 404) no debe descartar las demás
            print(f"    ⚠ No se pudo abrir {category['path']}: {exc}. Se omite la categoría.")
            continue
        strip_noise(soup)

        projects = []
        seen_urls = set()

        # Strategy: Find all card containers, which have heading + link
        cards = soup.find_all("div", class_="card")

        if cards:
            # New approach: cards with h3 heading and project link
            for card in cards:
                # Get heading (h2, h3, or h4)
                heading = card.find(["h2", "h3", "h4"])
                title = clean(heading.get_text()) if heading else ""

                if not title:
                    continue

                # Skip category headers or generic titles
                title_upper = title.upper()
                if any(kw in title_upper for kw in {"OBRAS", "REALIZADAS", "WELLMOD", "CATEGORÍA", "ENLACES", "CONTÁCTANOS"}):
                    continue

                # Buscar el link real de la ficha (no anclas #top ni el home).
                # Si la tarjeta no tiene ficha (proyecto "PRÓXIMAMENTE"), se
                # conserva igual con los datos de la tarjeta, sin descripción.
                link = next(
                    (a for a in card.find_all("a", href=True) if _is_project_link(a["href"])),
                    None,
                )

                if link is not None:
                    href = link["href"]
                    full_url = (href if href.startswith("http") else BASE_URL + href).split("#", 1)[0]
                    # Skip navigation links
                    if "/en/obras-" in full_url or full_url.rstrip("/").endswith("/en"):
                        continue
                    if full_url in seen_urls:
                        continue
                else:
                    full_url = ""  # proyecto sin página de detalle

                # Extract location from card paragraphs (second line after heading)
                # Card structure: <h3>Nombre</h3> <p>Ubicación</p> <p>Descubrila ➜</p>
                card_location = ""
                paras = card.find_all("p")
                if paras:
                    # First non-empty paragraph is usually the location
                    for p in paras:
                        text = clean(p.get_text())
                        if text and "descubrila" not in text.lower():
                            card_location = text
                            break

                # Extract other metrics from card content
                lines = get_lines(card)
                metrics = extract_project_metrics(lines)

                # Use card location if found, otherwise use extracted metric
                location = card_location or metrics.get("ubicacion", "")

                project = {
                    "nombre": title,
                    "url": full_url,
                    "categoria": metrics.get("categoria") or category["nombre"],
                    "ubicacion": location,
                    "tamano": metrics.get("tamano", ""),
                    "anio": metrics.get("anio", ""),
                }

                projects.append(project)
                if full_url:
                    seen_urls.add(full_url)
        else:
            # Fallback to old approach if no cards found
            for a in soup.find_all("a", href=True):
                href = a["href"]
                full_url = href if href.startswith("http") else BASE_URL + href

                if "/casa-" not in full_url and "/en/casa-" not in full_url:
                    if not any(kw in full_url for kw in ["/suite", "/paso", "/ramadita", "/energía", "/vista-", "/granja"]):
                        continue

                if "/en/obras-" in full_url or full_url.rstrip("/").endswith("/en"):
                    continue
                if full_url in seen_urls:
                    continue

                title_tag = a.find_previous(["h2", "h3", "h4"])
                title = clean(title_tag.get_text()) if title_tag else ""
                if not title:
                    continue
                title_upper = title.upper()
                if any(kw in title_upper for kw in {"OBRAS", "REALIZADAS", "WELLMOD", "CATEGORÍA"}):
                    if not any(kw in title_upper for kw in {"CASA", "SUITE", "TURISMO", "OFICINA", "GRANJA", "RAMADITA", "ENERGÍA"}):
                        continue

                container = find_card_container(a)
                lines = get_lines(container)

                if not title and lines:
                    title = clean(lines[0])

                metrics = extract_project_metrics(lines)

                project = {
                    "nombre": title,
                    "url": full_url,
                    "categoria": metrics.get("categoria") or category["nombre"],
                    "ubicacion": metrics.get("ubicacion", ""),
                    "tamano": metrics.get("tamano", ""),
                    "anio": metrics.get("anio", ""),
                }

                projects.append(project)
                seen_urls.add(full_url)

        obra_group = {
            "slug": category["slug"],
            "nombre": category["nombre"],
            "url": BASE_URL + category["path"],
            "proyectos": [],
        }

        for project in projects:
            if project["url"]:
                try:
                    detail = scrape_obra_detail(project["url"])
                except requests.RequestException as exc:
                    # La ficha de detalle falló (p.ej. 404): conservamos los datos de la tarjeta
                    print(f"    ⚠ No se pudo abrir {project['url']}: {exc}. Se usan datos de la tarjeta.")
                    detail = dict(_EMPTY_OBRA)
            else:
                # Proyecto sin ficha ("PRÓXIMAMENTE"): solo datos de la tarjeta
                detail = dict(_EMPTY_OBRA)
            # Merge detail with project, but preserve project values (from card metadata) when they exist
            merged = {**detail}
            for key in project:
                if project[key]:  # Keep card metadata if it has a value
                    merged[key] = project[key]
            obra_group["proyectos"].append(merged)
            sufijo = "" if project["url"] else "  (sin ficha — PRÓXIMAMENTE)"
            print(f"    ✓ {merged.get('nombre') or detail.get('nombre')}{sufijo}")

        obras.append(obra_group)

    return obras
