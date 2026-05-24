# Vanity HQ - Arquitectura

## Microservicios

| Servicio | Framework | Puerto | DB | Archivo principal | Lineas |
|----------|-----------|--------|----|-------------------|--------|
| **HQ Wrapper** | Flask | 5050 | SQLite | `vanity_hq_wrapper/app.py` | 790 |
| **Dashboard** | Flask | 5002 | CSV/JSON | `vanity_dashboard/app.py` | 861 |
| **Payroll** | Flask | 5051 | SQLite | `vanity_payroll/app.py` | 1592 |
| **Actas** | Flask | 5052 | SQLite | `vanity_actas/app.py` | 312 |
| **EmpReq** | Flask | 5053 | SQLite | `vanity_empreq/app.py` | 316 |
| **HR Manager** | Django+DRF | 8000 | PostgreSQL | `vanity_hrmgr/` | 240+81 |

## Autenticacion SSO

Flujo centralizado via HQ Wrapper:
1. Usuario hace login en HQ Wrapper (`/login`)
2. HQ Wrapper emite token URLSafeTimedSerializer firmado con `VANITY_HQ_SECRET_KEY`
3. Al lanzar un servicio (`/launch/<system_key>`), redirect con token en URL
4. Servicio下游 valida localmente, fallback a `/api/auth/validate-token` en HQ

Roles: Owner(100), Admin(80), Manager(60), Operador(40), Solo lectura(20), Socia(10)

Permisos: Por sistema > modulo > accion > scope(all/branch/own/assigned/none)

## Soporte PWA (Progressive Web App) y Redirección Seamless SSO

### Redirección Seamless en Producción
Para garantizar que el flujo de SSO sea totalmente transparente ("seamless") para el cliente externo desde internet:
- Los decoradores `login_required` y `require_permission` de los microservicios downstream redirigen solicitudes no autenticadas utilizando la URL pública del portal (`VANITY_HQ_PUBLIC_URL`, por ejemplo `https://vanityhq.soul23.cloud`) en lugar de la dirección IP/nombre interna de Docker (`HQ_BASE_URL`). Esto previene errores de "Connection Refused" en el navegador del usuario final.

### Soporte de Progressive Web App (PWA)
Se ha implementado compatibilidad con PWA en los servicios **HR Manager (Django)** y **EmpReq (Flask)**:
- **`manifest.json` y `service-worker.js` unificados**: Servidos a nivel raíz como templates dinámicos y responsivos, usando `start_url: "./"` para autoadaptarse tanto al dominio dedicado (`vanityerq.soul23.cloud`) como a la sub-ruta del HQ (`vanityhq.soul23.cloud/empleadas/`).
- **Registro Automático**: El layout común `templates/base.html` detecta y registra el service worker automáticamente en el navegador del cliente.
- **Estrategia de Caché**: El service worker implementa una estrategia de "Network First con fallback a Caché" para asegurar el funcionamiento sin conexión y una velocidad de carga neumórfica ágil para activos estáticos (`/static/css/dashboard.css` y `logo_cadrex.png`).
- **Despliegue Docker**: Todos los Dockerfiles copian recursivamente las carpetas compartidas `/templates` y `/static` al compilarse, garantizando la consistencia visual y de recursos en los contenedores aislados de VPS Coolify.

## Puertos y Rutas

### HQ Wrapper (5050)
- `/login` `/logout` - Auth
- `/hq` - Dashboard principal con system cards
- `/auth/hq?token=...` - SSO token validation
- `/launch/<system_key>` - Emite token y redirect
- `/users`, `/permissions`, `/audit` - Admin
- `/api/context/me` - Contexto de usuario actual (JSON)
- `/api/auth/validate-token` - Validacion de token (para downstream)
- `/api/permissions/effective`, `/api/permissions/check`
- `/api/audit/events` - Recibe eventos de auditoria

### Dashboard (5002)
- `/auth/hq` - SSO entry
- `/api/kpi`, `/api/sales_*`, `/api/staff_*` - KPIs y datos
- `/api/profitability`, `/api/config` - Config y rentabilidad
- `/api/filters` - Metadatos de filtros

### Payroll (5051)
- `/auth/hq` - SSO entry
- `/dashboard`, `/people`, `/people/<id>`, `/payments`, `/periods`
- `/people/new`, `/people/<id>/edit`, `/people/<id>/contract`
- `/payments/<id>/edit`, `/payments/<id>/receipt`, `/payments/export.csv`
- `/periods/<id>/generate`, `/periods/<id>/recalculate`
- API: `/api/people/*`, `/api/receipts/*`

### Actas (5052)
- `/auth/hq` - SSO entry
- `/dashboard`, `/actas`, `/actas/<id>`
- `/actas/nueva`, `/actas/<id>/editar`, `/actas/<id>/eliminar`

### EmpReq (5053)
- `/auth/hq` - SSO entry
- `/dashboard`, `/solicitudes`, `/solicitudes/<id>`
- `/solicitudes/nueva`, `/solicitudes/<id>/editar`

### HR Manager (8000)
- Admin: `/admin/`
- API: `/api/` (DRF con JWT + API Key)
- Empleados: `/empleados/`, `/empleados/crear/`, `/empleados/<id>/editar/`
- Solicitudes: `/solicitudes/`, `/solicitudes/pendientes/`
- Ausencias: `/ausencias/`, `/ausencias/registrar/`
- Sucursales: `/sucursales/`
- Reportes: `/reportes/`
- Mi espacio: `/mi-espacio/`, `/mi-perfil/`
- Telegram: `/telegram/webhook/`
- Auditoria: `/auditoria/`

## Infraestructura Docker

### Compose files
- `docker-compose.yml` - Produccion (Coolify sin proxy, Traefik maneja SSL)
- `docker-compose.dev.yml` - Desarrollo local con Nginx reverse proxy
- `docker-compose.override.yml` - Port mappings locales (auto-merge)

### Variables de entorno
- `.env` - Desarrollo local (gitignored)
- `.env.example` - Template para nuevos devs
- `.env.coolify` - Produccion Coolify con claves y URLs
- `.env.coolify.example` - Template Coolify sin claves

### Servicios Docker
| Servicio | Imagen | Dependencias |
|----------|--------|--------------|
| hq-wrapper | build | - |
| dashboard | build | - |
| payroll | build | hq-wrapper |
| actas | build | - |
| empreq | build | - |
| hrmgr-web | build | hrmgr-db, hrmgr-redis, payroll |
| hrmgr-celery | build | hrmgr-db, hrmgr-redis |
| hrmgr-db | postgres:15 | - |
| hrmgr-redis | redis:7-alpine | - |

## Estructura de Directorios

```
vanity_hq/
├── docker-compose.yml          # Produccion
├── docker-compose.dev.yml     # Desarrollo con nginx
├── docker-compose.override.yml # Port mappings locales
├── .env.example               # Template dev
├── .env.coolify.example       # Template produccion
├── .env.coolify               # Produccion con claves (gitignored)
├── nginx/
│   ├── nginx.conf             # Produccion (Coolify/Traefik)
│   ├── nginx.dev.conf         # Desarrollo local
│   └── ssl/                   # Certificados SSL
├── scripts/
│   ├── generate_ssl.sh        # Generar certificados
│   ├── setup_env_secrets.sh   # Generar secret keys
│   ├── verify_production_config.sh
│   ├── prepare_vps_deploy.sh
│   ├── test_deploy.sh
│   ├── levantar_local.sh
│   └── unify_config.sh
├── docs/
│   ├── architecture/           # PRD y arquitectura
│   └── deployment/            # Checklists y guias
├── vanity_hq_wrapper/         # Auth central (Flask, 790 lineas)
├── vanity_dashboard/          # Dashboard ventas (Flask, 861 lineas)
├── vanity_payroll/            # Nomina (Flask, 1592 lineas)
├── vanity_actas/              # Actas administrativas (Flask, 312 lineas)
├── vanity_empreq/            # Portal empleadas (Flask, 316 lineas)
└── vanity_hrmgr/              # HR Manager (Django, PostgreSQL)
```