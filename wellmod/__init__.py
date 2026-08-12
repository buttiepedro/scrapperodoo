"""Scraper modular de www.wellmod.com.ar.

Cada submódulo se encarga de una sección del sitio (home, nosotros, servicios,
faqs, tipologias, obras). `runner.run()` las orquesta y guarda el JSON.
"""

from .runner import run

__all__ = ["run"]
