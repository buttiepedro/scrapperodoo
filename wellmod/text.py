"""Helpers de limpieza de texto y extracción de métricas desde el HTML."""

import re

from bs4 import BeautifulSoup


def clean(text: str) -> str:
    """Normaliza espacios y elimina caracteres de control."""
    text = text or ""
    text = re.sub(r"[​‌‍﻿]", "", text)
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
