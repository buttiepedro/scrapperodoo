"""Cliente HTTP: descarga una página y devuelve su árbol BeautifulSoup."""

import time

import requests
from bs4 import BeautifulSoup

from .config import BASE_URL, DELAY, HEADERS


def get_soup(path: str) -> BeautifulSoup:
    url = path if path.startswith("http") else BASE_URL + path
    print(f"  GET {url}")
    time.sleep(DELAY)
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    # Forzar UTF-8 explícitamente para evitar detección errónea de encoding
    r.encoding = "utf-8"
    return BeautifulSoup(r.text, "lxml")
