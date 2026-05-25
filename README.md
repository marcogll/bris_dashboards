<p align="center">
  <img src="https://raw.githubusercontent.com/marcogll/mg_data_storage/refs/heads/main/soul23/logo/soul23_logo.svg" width="110" alt="Cadrex Dashboard">
</p>

<h1 align="center">Cadrex — Sistema de Gestión Operativa</h1>

<p align="center">
  Dashboard de producción, KPIs de ensamble, control de fixtures, kanban operativo y pipeline de datos estructurados.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12-3a3a3a?style=flat-square&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Flask-3a3a3a?style=flat-square&logo=flask&logoColor=white" alt="Flask">
  <img src="https://img.shields.io/badge/MySQL-8.4-3a3a3a?style=flat-square&logo=mysql&logoColor=white" alt="MySQL">
  <img src="https://img.shields.io/badge/Docker-3a3a3a?style=flat-square&logo=docker&logoColor=white" alt="Docker">
  <img src="https://img.shields.io/badge/Coolify-3a3a3a?style=flat-square&logo=coolify&logoColor=white" alt="Coolify">
  <img src="https://img.shields.io/badge/PWA-3a3a3a?style=flat-square&logo=pwa&logoColor=white" alt="PWA">
</p>

---

## Propósito

Este repositorio centraliza dos capas de trabajo:

1. **BRIS Dashboard (Flask)** — Dashboard de KPIs de ensamble, plan de acción, kanban, control de fixtures y gestión de datos curados.
2. **Pipeline de Datos Adriana** — Extracción desde Excel, normalización a CSV y carga estructurada a MySQL.

El objetivo es eliminar el seguimiento manual ("micromanagement"), digitalizar el control de mantenimiento de herramentales y centralizar las iniciativas de mejora continua para las líneas de ensamble.

---

## Stack Tecnológico

| Capa | Tecnología |
|------|------------|
| Backend | Python 3.12 + Flask + Gunicorn |
| Frontend | Jinja2 + Vanilla JS + CSS3 (Catppuccin Latte/Mocha) |
| Base de datos | MySQL 8.4 (pipeline Adriana) / CSV + JSON (dashboard) |
| AI Assistant | OpenRouter (Claude Haiku) vía `/api/chat` |
| PWA | `manifest.json` + `service-worker.js` (caché network-first) |
| Deploy | Docker + Docker Compose + Coolify (Traefik) |

---

## Estructura

```text
.
├── app.py                          # App principal Flask (BRIS Dashboard)
├── docker-compose.yml              # Stack de producción (Flask + MySQL)
├── Dockerfile
├── requirements.txt
├── data/
│   ├── stations.csv                # Datos de estaciones (ensamble)
│   ├── users.json                  # Usuarios locales (auth opcional)
│   ├── fallbacks/                  # JSON de respaldo cuando no hay CSV
│   └── raw/                        # Excel originales (fuentes)
├── templates/                      # Templates Jinja2
│   ├── base.html                   # Layout responsive con sidebar + PWA
│   ├── dashboard.html              # Dashboard maestro de KPIs
│   ├── produccion.html             # Vista de producción
│   ├── plan.html                   # Plan de acción
│   ├── partes.html                 # Catálogo de partes / BOM
│   ├── kanban.html                 # Alertas kanban
│   ├── diagrama.html               # Diagrama de operaciones / spaghetti
│   ├── datos.html                  # Gestión de datos curados (import/export)
│   ├── login.html                  # Login local (auth opcional)
│   ├── manifest.json               # PWA manifest
│   ├── service-worker.js           # Estrategia network-first
│   └── kadrix/                     # Módulo multiagente Kadrix
│       ├── hq.html, board.html, fixtures.html, projects.html, activity.html, analytics.html
├── kadrix/                         # Blueprint Kadrix
│   ├── __init__.py
│   ├── db.py                       # Queries MySQL
│   ├── views.py                    # Rutas Kanban, Fixtures, Projects
│   └── analytics.py                # Análisis y métricas
├── scripts/                        # Scripts auxiliares
│   └── extract_opus_data.py
├── adriana_projects/               # Pipeline de datos Adriana
│   ├── data/
│   │   ├── curated/                # CSVs normalizados
│   │   └── summary.json
│   ├── mysql/init/                 # Schemas SQL
│   └── scripts/
│       ├── build_adriana_dataset.py
│       └── load_mysql.py
└── docs/
    ├── ARCHITECTURE.md             # Arquitectura de software
    ├── INFRASTRUCTURE.md           # Infraestructura y deploy
    └── SECURITY.md                 # Autenticación, headers y secrets
```

---

## Características Principales

### Dashboard de Ensamble (`/`)
- Lectura de `data/stations.csv` con cálculo de:
  - Cuello de botella
  - Capacidad por hora y piezas por turno
  - Gap contra takt
  - Contenido total de trabajo
  - Rebalanceo sugerido moviendo operadores
- Gráficos interactivos con modales y tablas de datos
- Filtros por grupo de estaciones
- Soporte responsive (mobile sidebar con overlay)

### Gestión de Datos (`/datos`)
- Importación/exportación de datasets curados (CSV/XLSX)
- Templates descargables para cada dataset
- Datasets soportados: `balanceo`, `plan`, `kanban`, `demanda`, `desperdicios`, `throughput`

### Plan de Acción (`/plan`)
- Seguimiento de iniciativas de mejora continua
- Estados: `Pendiente`, `En progreso`, `Completado`, `Cancelado`

### Kanban y Alertas (`/kanban`)
- Alertas de inventario y partes críticas con días restantes

### Diagrama de Operaciones (`/diagrama`)
- Diagrama de flujo (spaghetti) de operaciones por línea
- Visualización de cycle times y conexiones entre estaciones

### Control de Fixtures (`/kadrix/fixtures`)
- Base de datos visual de herramentales críticos
- Estados: Disponible, Reparación, PM

### Tableros Kanban (`/kadrix/board/<id>`)
- Tareas con drag-and-drop entre columnas
- Creación rápida de tareas

### Bri AI Chat (`/api/chat`)
- Widget de asistencia IA integrado en todas las páginas
- Backend vía OpenRouter (Claude Haiku)

### Temas Visuales
- Toggle dark/light (Catppuccin Mocha / Latte)
- Persistencia en `localStorage`
- Diseño neumórfico responsive

---

## Variables de Entorno

Copiar `.env.example` a `.env` y ajustar:

```env
# === App Core ===
APP_TITLE=Cadrex — Dashboard
PORT=8743
SECRET_KEY=change-me-en-produccion
FLASK_ENV=production

# === Datos de Ensamble ===
DATA_FILE=/app/data/stations.csv
AVAILABLE_SECONDS=39900
TAKT_SECONDS=2216.666667
UPLOAD_SECRET=                    # Clave opcional para upload vía UI

# === Auth Local (Opcional) ===
LOGIN_REQUIRED=false              # true para activar login

# === MySQL (Pipeline Adriana) ===
MYSQL_HOST=mysql
MYSQL_PORT=3306
MYSQL_DATABASE=bris_adriana
MYSQL_USER=bris_user
MYSQL_PASSWORD=change-me
MYSQL_ROOT_PASSWORD=change-root

# === OpenRouter (Bri AI) ===
OPENROUTER_API_KEY=sk-or-v1-...
OPENROUTER_MODEL=anthropic/claude-3-haiku
```

Ver [docs/SECURITY.md](docs/SECURITY.md) para recomendaciones de secrets.

---

## Ejecución Local

```bash
bash scripts/run_local.sh
```

Abrir: `http://127.0.0.1:5001`

Arranque manual equivalente:
```bash
PORT=5001 .venv/bin/python app.py
```

---

## Docker Compose

### Producción (Coolify)

```bash
cp .env.example .env
# Editar .env con tus secrets
docker compose up --build
```

Healthcheck disponible en `/healthz`.

### Con MySQL

El compose principal (`docker-compose.yml`) levanta BRIS Dashboard. Si requieres MySQL para el pipeline Adriana, extender el compose o usar un compose adicional con el servicio `mysql` y el perfil `import`:

```bash
# Ejemplo de importación de CSVs curados a MySQL
docker compose --profile import run --rm adriana-importer
```

---

## Pipeline de Datos Adriana

### Generar CSVs curados

```bash
python3 adriana_projects/scripts/build_adriana_dataset.py
```

Genera:
- `adriana_projects/data/raw_csv/` — exportación por hoja
- `adriana_projects/data/curated/` — datasets normalizados
- `adriana_projects/data/summary.json` — conteo de registros

### Cargar a MySQL

```bash
docker compose --profile import run --rm adriana-importer
```

La carga trunca y recarga las tablas administradas por el pipeline.

---

## PWA (Progressive Web App)

- **Manifest**: servido en `/manifest.json` con `start_url: "./"`
- **Service Worker**: `/service-worker.js` con estrategia *Network First + fallback a caché*
- **Registro automático** en `templates/base.html`
- Compatible con despliegue en sub-rutas y dominios dedicados

---

## Documentación Técnica

| Documento | Contenido |
|-----------|-----------|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Arquitectura de software, módulos y flujos de datos |
| [docs/INFRASTRUCTURE.md](docs/INFRASTRUCTURE.md) | Infraestructura Docker, redes, deploy y healthchecks |
| [docs/SECURITY.md](docs/SECURITY.md) | Autenticación, headers de seguridad, CSP y secrets |

---

## Notas de Mantenimiento

- Los Excel originales se conservan como fuentes en `data/raw/`.
- `raw_rows` permite auditoría cuando una hoja no tiene estructura limpia.
- Las tablas curadas son para análisis y consultas operativas.
- Si cambia el formato de una hoja, ajustar `build_adriana_dataset.py` y regenerar.
- El login local es **opt-in** (`LOGIN_REQUIRED=true`). Por defecto la app es pública para facilitar demos y acceso interno.
