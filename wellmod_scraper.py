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

BASE_URL = os.getenv("WELLMOD_BASE_URL", "https://wellmod.odoo.com").rstrip("/")
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
    return re.sub(r"\s+", " ", text or "").strip()


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

    # Estadísticas: buscar patrones "número + etiqueta"
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

    # Descripción principal — solo párrafos <p> para evitar mezclar headings
    descripcion = ""
    KEYWORDS = ("modular transportable", "arquitectura modular", "preconstruid", "residencial, comercial")
    for p in soup.find_all("p"):
        t = clean(p.get_text())
        if any(kw in t.lower() for kw in KEYWORDS) and 60 < len(t) < 600:
            descripcion = t
            break

    # Fallback: primer párrafo largo que no sea menú/footer/legal
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

    # Historia: pares año → hito en el texto lineal
    historia = []
    year_re = re.compile(r"^\d{4}$")
    i = 0
    while i < len(lines):
        if year_re.match(lines[i]) and i + 1 < len(lines):
            año = lines[i]
            hito = lines[i + 1]
            # Evitar duplicados consecutivos
            if not historia or historia[-1]["año"] != año or historia[-1]["hito"] != hito:
                historia.append({"año": año, "hito": hito})
            i += 2
        else:
            i += 1

    # Fundadores y testimonios
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
            fundadores.append({
                "nombre": nombre,
                "testimonio": " ".join(testimonio_parts)
            })

    # Descripción general de la empresa (Brief)
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

        # Detectar categoría
        if line.upper() in CATEGORIAS:
            current_cat = line.upper()
            i += 1
            continue

        # Detectar preguntas (pueden venir varias seguidas sin respuesta en medio)
        preguntas = re.findall(r"¿[^¿?]+\?", line)
        if preguntas:
            # La respuesta puede estar en la misma línea después de las preguntas
            # o en las siguientes líneas
            respuesta = re.sub(r"¿[^¿?]+\?", "", line).strip()

            if not respuesta:
                # Buscar respuesta en líneas siguientes
                j = i + 1
                while j < len(lines) and j < i + 8:
                    candidate = lines[j]
                    # La respuesta no empieza con ¿ y tiene sustancia
                    if not candidate.startswith("¿") and len(candidate) > 15:
                        respuesta = candidate
                        break
                    j += 1

            for pregunta in preguntas:
                faqs.append({
                    "categoria": current_cat,
                    "pregunta": clean(pregunta),
                    "respuesta": clean(respuesta)
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
        # Los links de detalle contienen /en/w
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

    # Nombre: primer H1 o H2 significativo
    for tag in soup.find_all(re.compile(r"^h[12]$")):
        t = clean(tag.get_text())
        if t and len(t) < 80 and "wellmod" not in t.lower() and "tipolog" not in t.lower():
            result["nombre"] = t
            break

    # Precio
    result["precio"] = extract_price(full_text)

    # Descripción: primer párrafo largo antes del precio, sin precios ni ruido legal
    for p in soup.find_all("p"):
        t = clean(p.get_text())
        if (
            len(t) > 50
            and "U$D" not in t
            and "derechos reservados" not in t
            and "Odoo" not in t
            and "cookie" not in t.lower()
        ):
            result["descripcion"] = t
            break

    # Parsear secciones: Incluye / Exclusiones / Opcionales / Opcionales Premium
    # El HTML de Odoo puede presentar bullets como:
    #   a) Carácter standalone en su propia línea (para Incluye)
    #   b) "• texto" al inicio de línea (para Exclusiones/Opcionales)
    # Estrategia: acumular texto por sección y luego splitear por •
    SECTION_PATTERNS = [
        (re.compile(r"^opcionales?\s*premium", re.I), "opcionales_premium"),
        (re.compile(r"^opcionales?", re.I), "opcionales"),
        (re.compile(r"^exclusiones?", re.I), "exclusiones"),
        (re.compile(r"^incluye", re.I), "incluye"),
    ]

    # Palabras que marcan fin del contenido de tipología (ruido de navegación)
    STOP_WORDS = {"anterior", "siguiente", "antersiguiente", "copyright"}

    current_section = None
    section_buffer: dict[str, list[str]] = {
        "incluye": [], "exclusiones": [], "opcionales": [], "opcionales_premium": []
    }

    for line in lines:
        # Stop si hay ruido de navegación
        if line.lower() in STOP_WORDS:
            break

        # Detectar sección
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

    # Post-procesar cada sección: unir el buffer y splitear por bullet
    BULLET_RE = re.compile(r"[•\u00f2\u25cf\u2022]")  # •, ò, ●, •

    def parse_bullet_items(raw_lines: list[str]) -> list[str]:
        combined = " ".join(raw_lines)
        # Splitear por bullet (puede ser inline o al inicio)
        parts = BULLET_RE.split(combined)
        items = []
        for part in parts:
            # Limpiar y unir label: descripción (label en negrita separado del valor)
            cleaned = clean(part)
            if cleaned and len(cleaned) > 2:
                # Si el item tiene un "Label: valor" en dos partes pegadas, está bien
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
            "version": "1.0"
        }
    }

    print("\n[1/5] Home →")
    output["empresa"] = scrape_home()

    print("\n[2/5] Nosotros →")
    output["nosotros"] = scrape_nosotros()

    print("\n[3/5] Servicios →")
    output["servicios"] = scrape_servicios()

    print("\n[4/5] FAQs →")
    output["faqs"] = scrape_faqs()

    print("\n[5/5] Tipologías →")
    tipologia_urls = scrape_tipologias_catalog()
    print(f"  → {len(tipologia_urls)} productos encontrados")

    tipologias = []
    for url in tipologia_urls:
        detail = scrape_tipologia_detail(url)
        tipologias.append(detail)
        print(f"  ✓ {detail['nombre'] or url}")

    output["tipologias"] = tipologias

    output["contacto"] = {
        "whatsapp_numero": "+54 9 351 816-0094",
        "whatsapp_url": "https://wa.me/5493518160094",
        "web": BASE_URL,
        "mensaje_sugerido_tipologias": (
            "¡Hola! Me gustaría recibir información sobre "
            "las distintas tipologías Wellmod. ¡Gracias!"
        )
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 60}")
    print(f"  ✓ JSON guardado en: {OUTPUT_FILE}")
    print(f"  Tipologías: {len(tipologias)}")
    print(f"  Servicios:  {len(output['servicios'])}")
    print(f"  FAQs:       {len(output['faqs'])}")
    print(f"  Hitos hist: {len(output['nosotros']['historia'])}")
    print("=" * 60)


if __name__ == "__main__":
    main()
