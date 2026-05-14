# Wellmod Cached API

API cacheada para exponer la base de conocimiento de Wellmod en JSON.

## Objetivo

Esta solución implementa un patrón de caché estable:

1. Un scraper actualiza periódicamente el archivo JSON local.
2. La API solo sirve el último JSON cacheado.
3. n8n consume por HTTP de forma rápida y confiable.

## Arquitectura

- Scraper: `wellmod_scraper.py`
- API: `wellmod_cached_api.py`
- Runtime: Docker + FastAPI + Uvicorn
- Cache JSON: `data/wellmod_knowledge_base.json`

## Secciones del JSON

### Empresarial
- `empresa`: Descripción de la empresa, pilares, estadísticas
- `nosotros`: Historia e hitos históricos
- `servicios`: Lista de servicios ofrecidos
- `faqs`: Preguntas frecuentes

### Catálogos
- `tipologias`: Modelos/tipos de arquitectura modular (11 productos)
- `obras`: Proyectos realizados por categoría (19 proyectos en 4 categorías)
  - **Viviendas**: 10 proyectos
  - **Turismo**: 4 proyectos
  - **Oficinas**: 4 proyectos
  - **Oil and Gas**: 1 proyecto

Cada obra incluye: nombre, URL, categoría, ubicación, tamaño (m²), año, descripción

## Endpoints

### 1) `GET /health`
Chequeo de estado del servicio.

Respuesta ejemplo:

```json
{
  "ok": true,
  "service": "wellmod-cached-api",
  "utc": "2026-05-08T13:43:00.803606+00:00",
  "json_exists": true
}
```

Campos:
- `ok`: estado general
- `service`: nombre del servicio
- `utc`: timestamp UTC actual
- `json_exists`: indica si existe el cache JSON en disco

---

### 2) `GET /wellmod/knowledge-base`
Devuelve el JSON completo cacheado.

Uso principal: consumir desde n8n con un nodo HTTP Request.

Errores comunes:
- `404`: no existe el archivo de caché
- `500`: JSON inválido/corrupto

---

### 3) `GET /wellmod/metadata`
Devuelve un resumen liviano del cache.

Respuesta ejemplo:

```json
{
  "source": "https://wellmod.odoo.com",
  "scraped_at": "2026-05-14T12:43:07.123456",
  "version": "1.0",
  "tipologias": 11,
  "servicios": 9,
  "faqs": 20,
  "obras_categorias": 4,
  "obras": 19
}
```

Campos:
- `obras_categorias`: Número de categorías de obras (Viviendas, Turismo, Oficinas, Oil and Gas)
- `obras`: Número total de proyectos realizados

Uso recomendado: monitoreo o validación rápida sin descargar todo el JSON.

---

### 4) `POST /wellmod/refresh`
Ejecuta manualmente el scraper y regenera el cache.

Requiere header:

- `Authorization: Bearer <WELLMOD_REFRESH_TOKEN>`

Comportamiento:
- `403`: token no configurado en entorno
- `401`: token inválido
- `500`: fallo del scraper
- `504`: timeout del scraper

## Variables de entorno (`.env`)

```env
# API
WELLMOD_API_HOST=0.0.0.0
WELLMOD_API_PORT=8080

# Paths (inside container)
WELLMOD_DATA_DIR=/app/data
WELLMOD_OUTPUT_FILE=/app/data/wellmod_knowledge_base.json
WELLMOD_JSON_FILE=/app/data/wellmod_knowledge_base.json
WELLMOD_SCRAPER_FILE=/app/wellmod_scraper.py

# Scraper behavior
WELLMOD_REQUEST_DELAY=1.5
RUN_SCRAPER_ON_START=true
AUTO_REFRESH_EVERY_HOURS=24

# Optional: secure manual refresh endpoint
WELLMOD_REFRESH_TOKEN=change-me-now
```

## Estructura de "Obras" en el JSON

Cada proyecto contiene:

```json
{
  "obras": [
    {
      "slug": "viviendas",
      "nombre": "Viviendas",
      "url": "https://wellmod.odoo.com/obras-viviendas",
      "proyectos": [
        {
          "nombre": "CASA MR",
          "url": "https://wellmod.odoo.com/casa-mr",
          "categoria": "Viviendas",
          "ubicacion": "San Clemente, Córdoba",
          "tamano": "...",
          "anio": "...",
          "descripcion": "..."
        }
      ]
    }
  ]
}
```

Campos:
- `nombre`: Nombre del proyecto
- `ubicacion`: Localidad/Región (extraída de las tarjetas de categoría)
- `tamano`: Superficie en m² (cuando disponible)
- `anio`: Año de desarrollo (cuando disponible)
- `descripcion`: Descripción del proyecto desde la ficha de detalle

## Ejecutar con Docker

### Levantar

```bash
docker compose up -d --build
```

### Ver estado

```bash
docker compose ps
```

### Ver logs

```bash
docker compose logs -f wellmod-api
```

### Detener

```bash
docker compose down
```

## Consumo desde n8n

Nodo HTTP Request:

- Method: `GET`
- URL: `http://<tu_host>:8080/wellmod/knowledge-base`
- Response Format: `JSON`

Opcional (refresh manual):

- Method: `POST`
- URL: `http://<tu_host>:8080/wellmod/refresh`
- Header: `Authorization: Bearer <WELLMOD_REFRESH_TOKEN>`

## Flujo recomendado

1. n8n consulta `GET /wellmod/knowledge-base` para usar contexto.
2. El contenedor refresca automáticamente cada `AUTO_REFRESH_EVERY_HOURS`.
3. Si necesitas forzar actualización, llama `POST /wellmod/refresh`.

## Contenido scrapeado

### Páginas del sitio
- **Home** (`/`): Información general de la empresa
- **Nosotros** (`/about-us`): Historia e hitos
- **Servicios** (`/servicios`): Servicios ofrecidos
- **FAQs** (`/faqs`): Preguntas frecuentes
- **Tipologías** (`/tipologias`): Modelos de arquitectura modular

### Obras realizadas
Se scrapeean las 4 categorías principales:
1. **Viviendas** → 10 proyectos (casas modulares, residenciales)
2. **Turismo** → 4 proyectos (resorts, posadas, suites turísticas)
3. **Oficinas** → 4 proyectos (espacios corporativos, administrativos)
4. **Oil and Gas** → 1 proyecto (infraestructura para industria petrolera)

Cada proyecto incluye metadatos de la tarjeta (ubicación, tamaño) y descripción completa desde la página de detalle.

## Notas

- El scraper guarda siempre el último estado en `data/wellmod_knowledge_base.json`.
- Para compartir el proyecto, no publiques tokens reales en `.env`.
- Las ubicaciones se extraen desde las tarjetas de categoría (confiables).
- Los tamaños y años se extraen tanto de tarjetas como de páginas de detalle.
