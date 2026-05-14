#!/usr/bin/env python3
"""
Scraper para wellmod.odoo.com
Genera wellmod_knowledge_base.json con la base de conocimiento de la empresa.

Uso:
    python wellmod_scraper.py

Dependencias:
    pip install requests beautifulsoup4 lxml
"""

import re
import time
import json
import os
from datetime import datetime

import requests
from bs4 import BeautifulSoup

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURACIÓN
# ─────────────────────────────────────────────────────────────────────────────

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
    {"slug": "oil-and-gas", "path": "/obras-oil-and-gas", "nombre": "Oil and Gas"},
]


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def get_soup(path: str) -> BeautifulSoup:
    url = path if path.startswith("http") else BASE_URL + path
    print(f"  GET {url}")
    time.sleep(DELAY)
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    # Forzar UTF-8 explícitamente para evitar detección errónea de encoding
    r.encoding = "utf-8"
    return BeautifulSoup(r.text, "lxml")


def clean(text: str) -> str:
    """Normaliza espacios y elimina caracteres de control."""
    text = text or ""
    text = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def strip_noise(soup: BeautifulSoup) -> None:
    """Elimina tags que aportan ruido (scripts, estilos, nav, footer)."""
    for tag in soup(["script", "style", "noscript", "nav", "footer", "meta", "link"]):
        tag.decompose()


def get_lines(soup: BeautifulSoup) -> list[str]:
    """Extrae líneas de texto no vacías del soup."""
    return [clean(l) for l in soup.get_text(separator="\n").split("\n") if clean(l)]


def extract_price(text: str) -> str:
    m = re.search(r"(U\$D\s*[\d.,]+\s*\+\s*IVA)", text)
    return clean(m.group(1)) if m else ""


def extract_whatsapp(soup: BeautifulSoup) -> str:
    for a in soup.find_all("a", href=True):
        if "wa.link" in a["href"] or "wa.me" in a["href"]:
            return a["href"]
    return ""


def find_card_container(anchor) -> object:
    """Encuentra el contenedor más específico de una tarjeta con título + link."""
    candidates = []
    current = anchor.parent

    while current and getattr(current, "name", None) not in ("main", "body", "html"):
        if current.find(["h2", "h3", "h4"]) and current.find("a", href=anchor.get("href")):
            lines = get_lines(current)
            if 2 <= len(lines) <= 25:
                candidates.append((len(lines), current))
        current = current.parent

    if candidates:
        candidates.sort(key=lambda item: item[0])
        return candidates[0][1]

    return anchor.parent


def looks_like_location(text: str) -> bool:
    text = clean(text)
    if not text or len(text) < 4:
        return False
    if text.lower() in {"descubrila ➜", "descubrirla ➜", "ver más", "ver mas"}:
        return False
    if re.fullmatch(r"\d{4}", text):
        return False
    if re.search(r"\b\d+(?:[.,]\d+)?\s*m(?:²|2)\b", text, re.I):
        return False
    if "copyright" in text.lower() or "odoo" in text.lower():
        return False
    return any(ch.isalpha() for ch in text)


def extract_project_metrics(lines: list[str]) -> dict[str, str]:
    data = {"categoria": "", "ubicacion": "", "anio": "", "tamano": ""}

    for idx, line in enumerate(lines):
        current = clean(line)
        lower = current.lower()

        if not data["categoria"] and lower in {"vivienda", "viviendas", "turismo", "oficinas", "oil and gas"}:
            data["categoria"] = current
            continue

        if not data["anio"]:
            m = re.fullmatch(r"(19|20)\d{2}", current)
            if m:
                data["anio"] = current
                continue

        if not data["tamano"]:
            m = re.search(r"\b\d+(?:[.,]\d+)?\s*m(?:²|2)\b", current, re.I)
            if m:
                data["tamano"] = clean(m.group(0)).replace(" ", "")
                continue

        if not data["ubicacion"] and looks_like_location(current):
            if idx > 0 and lines[idx - 1].strip().lower() in {data["categoria"].lower(), ""}:
                continue
            if any(token in lower for token in ("descubr", "galería", "galeria", "contact", "home")):
                continue
            if len(current) > 90:
                continue
            if re.search(r"\b(19|20)\d{2}\b", current):
                continue
            data["ubicacion"] = current

    return data


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
        soup = get_soup(category["path"])
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
                
                # Find the project link within this card
                link = card.find("a", href=True)
                if not link:
                    continue
                    
                href = link["href"]
                full_url = href if href.startswith("http") else BASE_URL + href
                
                # Skip navigation links
                if "/en/obras-" in full_url or full_url.rstrip("/").endswith("/en"):
                    continue
                if full_url in seen_urls:
                    continue
                
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
            detail = scrape_obra_detail(project["url"])
            # Merge detail with project, but preserve project values (from card metadata) when they exist
            merged = {**detail}
            for key in project:
                if project[key]:  # Keep card metadata if it has a value
                    merged[key] = project[key]
            obra_group["proyectos"].append(merged)
            print(f"    ✓ {merged.get('nombre') or detail.get('nombre')}")

        obras.append(obra_group)

    return obras


# ─────────────────────────────────────────────────────────────────────────────
# HOME
# ─────────────────────────────────────────────────────────────────────────────

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


# ─────────────────────────────────────────────────────────────────────────────
# NOSOTROS
# ─────────────────────────────────────────────────────────────────────────────

def scrape_nosotros() -> dict:
    soup = get_soup("/about-us")
    strip_noise(soup)
    lines = get_lines(soup)

    historia = []
    year_re = re.compile(r"^\d{4}$")
    i = 0
    while i < len(lines):
        if year_re.match(lines[i]) and i + 1 < len(lines):
            año = lines[i]
            hito = lines[i + 1]
            if not historia or historia[-1]["año"] != año or historia[-1]["hito"] != hito:
                historia.append({"año": año, "hito": hito})
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


# ─────────────────────────────────────────────────────────────────────────────
# SERVICIOS
# ─────────────────────────────────────────────────────────────────────────────

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


# ─────────────────────────────────────────────────────────────────────────────
# FAQs
# ─────────────────────────────────────────────────────────────────────────────

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


# ─────────────────────────────────────────────────────────────────────────────
# TIPOLOGÍAS — CATÁLOGO
# ─────────────────────────────────────────────────────────────────────────────

def scrape_tipologias_catalog() -> list[str]:
    """
    Extrae las URLs de detalle de cada tipología desde la página del catálogo.
    Retorna lista de paths relativos o URLs absolutas.
    """
    soup = get_soup("/tipologias")
    urls = []
    seen = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/en/w" in href and href not in seen:
            seen.add(href)
            urls.append(href if href.startswith("http") else BASE_URL + href)

    if not urls:
        print("  ⚠ No se encontraron links dinámicamente. Usando URLs estáticas de fallback.")
        urls = [BASE_URL + p for p in TIPOLOGIAS_FALLBACK]

    return urls


# ─────────────────────────────────────────────────────────────────────────────
# TIPOLOGÍAS — DETALLE
# ─────────────────────────────────────────────────────────────────────────────

def parse_section_items(lines: list[str], section_name: str, stop_sections: set[str]) -> list[str]:
    """Extrae bullets de una sección específica del texto lineal."""
    items = []
    inside = False

    for line in lines:
        lower = line.lower().strip("• -")

        if lower == section_name.lower():
            inside = True
            continue

        if inside:
            if lower in {s.lower() for s in stop_sections}:
                break
            if line.startswith("•") or (line.startswith("-") and len(line) > 3):
                item = re.sub(r"^[•\-]\s*", "", line).strip()
                if item:
                    items.append(item)

    return items


def scrape_tipologia_detail(url: str) -> dict:
    soup = get_soup(url)
    strip_noise(soup)
    lines = get_lines(soup)
    full_text = "\n".join(lines)

    result = {
        "url": url,
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

    BULLET_RE = re.compile(r"[•\u00f2\u25cf\u2022]")

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


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
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
    output["empresa"] = scrape_home()

    print("\n[2/6] Nosotros →")
    output["nosotros"] = scrape_nosotros()

    print("\n[3/6] Servicios →")
    output["servicios"] = scrape_servicios()

    print("\n[4/6] FAQs →")
    output["faqs"] = scrape_faqs()

    print("\n[5/6] Tipologías →")
    tipologia_urls = scrape_tipologias_catalog()
    print(f"  → {len(tipologia_urls)} productos encontrados")

    tipologias = []
    for url in tipologia_urls:
        detail = scrape_tipologia_detail(url)
        tipologias.append(detail)
        print(f"  ✓ {detail['nombre'] or url}")

    output["tipologias"] = tipologias

    print("\n[6/6] Obras →")
    obras = scrape_obras_catalog()
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

    print(f"\n{'=' * 60}")
    print(f"  ✓ JSON guardado en: {OUTPUT_FILE}")
    print(f"  Tipologías: {len(tipologias)}")
    print(f"  Obras:      {sum(len(cat['proyectos']) for cat in obras)}")
    print(f"  Servicios:  {len(output['servicios'])}")
    print(f"  FAQs:       {len(output['faqs'])}")
    print(f"  Hitos hist: {len(output['nosotros']['historia'])}")
    print("=" * 60)


if __name__ == "__main__":
    main()
