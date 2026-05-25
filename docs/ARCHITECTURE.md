# Arquitectura — Cadrex

## Visión General

Cadrex es una aplicación Flask monolítica con dos subsistemas principales:

1. **BRIS Dashboard** — Aplicación principal para KPIs de producción, gestión de datos curados y control de fixtures.
2. **Pipeline Adriana** — ETL desde Excel a CSV curados y carga en MySQL.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              Usuario / Navegador                        │
│  (PWA, Responsive, Theme Toggle, Bri AI Chat)                          │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
                           ┌────────────────┐
                           │  Coolify       │
                           │  + Traefik     │
                           │  (SSL/Proxy)   │
                           └───────┬────────┘
                                   │
                                   ▼
                          ┌────────────────┐
                          │ BRIS Dashboard │
                          │ Flask + Gunicorn│
                          │    :8743       │
                          └───────┬────────┘
                                  │
              ┌───────────────────┼───────────────────┐
              ▼                   ▼                   ▼
      ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
      │ data/        │   │ templates/   │   │ MySQL 8.4    │
      │ (CSV/JSON)   │   │ (Jinja2)     │   │ (Pipeline)   │
      └──────────────┘   └──────────────┘   └──────────────┘
```

---

## BRIS Dashboard — Componentes

### Capa de Presentación (Templates Jinja2)

| Ruta | Template | Propósito |
|------|----------|-----------|
| `/` | `dashboard.html` / `dashboard_master.html` | KPIs de ensamble, gráficos, filtros |
| `/produccion` | `produccion.html` | Vista de producción diaria |
| `/plan` | `plan.html` | Plan de acción y seguimiento |
| `/partes` | `partes.html` | BOM y catálogo de partes |
| `/kanban` | `kanban.html` | Alertas de inventario |
| `/diagrama` | `diagrama.html` | Diagrama de operaciones / spaghetti |
| `/datos` | `datos.html` | Gestión de datasets curados (import/export) |
| `/login` | `login.html` | Auth local (opt-in) |
| `/kadrix/*` | `kadrix/*.html` | Kanban boards, fixtures, projects, activity, analytics |

**Base layout (`base.html`)**:
- Sidebar responsive con breakpoint `1024px`
- Mobile menu toggle + overlay (`sidebar-overlay`)
- Theme toggle (dark/light) persistido en `localStorage`
- Registro automático de Service Worker para PWA
- Widget de chat Bri AI (integrado en todas las páginas)

### Capa de Aplicación (`app.py`)

| Módulo | Responsabilidad |
|--------|-----------------|
| `Config` | Variables de entorno, defaults, paths |
| `Auth` | Login opcional (`LOGIN_REQUIRED`), sessions Flask, `users.json` |
| `Security Headers` | CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy |
| `Data Models` | `Station` dataclass, parsing de CSV |
| `KPI Engine` | Cálculo de bottleneck, takt, rebalanceo, throughput |
| `API REST` | `/api/*` endpoints para métricas, estaciones, producción, BOM, demanda, chat |
| `Data Management` | Import/export de CSV/XLSX para datasets curados |
| `Healthcheck` | `/healthz` para orquestadores (Coolify, Docker) |

### Blueprint Kadrix (`kadrix/`)

Extensión modular dentro de BRIS Dashboard:

- **`views.py`**: Rutas para tableros kanban, fixtures, projects, activity feed
- **`db.py`**: Queries parametrizadas a MySQL
- **`analytics.py`**: Agregaciones y métricas de utilización

Registrado como `kadrix_bp` con prefix implícito vía rutas absolutas en el blueprint.

---

## Pipeline de Datos Adriana

### Flujo ETL

```
Excel (.xlsx) en data/raw/
        │
        ▼
┌─────────────────────────────┐
│ build_adriana_dataset.py    │
│  - Detección automática de  │
│    hojas y estructuras      │
│  - Normalización a CSV      │
└─────────────┬───────────────┘
              ▼
    ┌─────────────────┐
    │  CSV Curados    │
    │  (7 datasets)   │
    └────────┬────────┘
             ▼
┌─────────────────────────────┐
│ load_mysql.py               │
│  - TRUNCATE + LOAD DATA     │
│  - Vistas analíticas        │
└─────────────────────────────┘
```

### Datasets Curados

| Dataset | Tabla MySQL | Descripción |
|---------|-------------|-------------|
| `source_sheets` | `source_sheets` | Inventario de archivos procesados |
| `parts` | `parts` | Catálogo consolidado de números de parte |
| `bom_items` | `bom_items` | Relaciones BOM, inventario, lead times |
| `pfep_items` | `pfep_items` | Plan For Every Part (rutas, bins, carts) |
| `work_center_operations` | `work_center_operations` | Operaciones, standard rate, crew size |
| `station_materials` | `station_materials` | Materiales por estación y paso |
| `kanban_notifications` | `kanban_notifications` | Alertas con días restantes |

### Vistas Analíticas

- `v_material_shortages` — materiales con riesgo por disponibilidad o lead time alto
- `v_station_load` — carga por estación y cantidad de partes
- `v_work_center_bottlenecks` — work centers ordenados por carga

---

## PWA y Responsive Design

### Progressive Web App

- **Manifest dinámico**: servido desde Flask con `start_url: "./"` para adaptarse a path-based routing
- **Service Worker**: estrategia *Network First con fallback a caché* para activos estáticos (`/static/css/dashboard.css`, `logo_cadrex.png`)
- **Scope**: funciona tanto en dominio dedicado como en sub-ruta

### Responsive Breakpoints

| Breakpoint | Cambios |
|------------|---------|
| `≤1024px` | Sidebar colapsa a off-canvas con toggle hamburguesa |
| `≤640px` | Header compacto, search oculto, botón "New" oculto, theme toggle oculto |

El layout previene scroll horizontal con `overflow-x: hidden` en `html, body`.

---

## Bri AI Chat

Integración de asistente IA en todas las páginas:

- **Frontend**: Widget flotante en `base.html` (JS vanilla)
- **Backend**: Endpoint `/api/chat` en `app.py`
- **Provider**: OpenRouter (`anthropic/claude-3-haiku` por defecto)
- **Configuración**: `OPENROUTER_API_KEY` y `OPENROUTER_MODEL`

---

## Diagrama de Dependencias

```text
app.py (BRIS Dashboard)
  ├─ kadrix_bp (kadrix/views.py)
  │   ├─ kadrix.db (MySQL queries)
  │   └─ kadrix.analytics (agregaciones)
  ├─ data/stations.csv (KPIs ensamble)
  ├─ data/users.json (auth local)
  ├─ adriana_projects/data/curated/*.csv (datasets)
  └─ templates/ (Jinja2)
```
