#!/usr/bin/env python3
"""
Entry-point del scraper de wellmod.odoo.com.

La lógica está dividida en el paquete `wellmod/` (un módulo por sección del
sitio). Este archivo se conserva como punto de entrada para mantener la
compatibilidad con Docker y con el endpoint `POST /wellmod/refresh`, que
invocan `python wellmod_scraper.py`.

Uso:
    python wellmod_scraper.py

Dependencias:
    pip install requests beautifulsoup4 lxml
"""

from wellmod import run

if __name__ == "__main__":
    run()
