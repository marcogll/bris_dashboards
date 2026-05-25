# Vanity HQ

Microservicios de nominas, RRHH, ventas y solicitudes para Vanity Nail Salon.

## Arquitectura

| Servicio | Puerto | Framework | Descripcion |
|---|---|---|---|
| HQ Wrapper | 5050 | Flask | Auth centralizado SSO, RBAC, lanzador |
| Dashboard | 5002 | Flask | KPIs de ventas, rendimiento staff |
| Payroll | 5051 | Flask | Nomina, pagos, recibos |
| HRMgr | 8000 | Django | Empleadas, vacaciones, permisos |
| Actas | 5052 | Flask | Actas administrativas |
| EmpReq | 5053 | Flask | Solicitudes de vacaciones/permisos |

## Stack

- Python 3.12, Flask, Django, SQLite, PostgreSQL
- Supabase (auth sessions, datos centralizados)
- Docker Compose + Coolify para deploy
- SSO via itsdangerous tokens (+ Supabase sessions)

## Estructura

```
vanity_hq/
├── vanity_hq_wrapper/        # Auth central, launcher, RBAC
├── vanity_dashboard/          # KPIs ventas, citas, rendimiento
├── vanity_payroll/            # Nomina, pagos, recibos
├── vanity_hrmgr/              # RRHH Django
├── vanity_actas/              # Actas administrativas
├── vanity_empreq/             # Solicitudes empleadas
├── vanity_common/             # Auth, sesiones Supabase, modelos compartidos
├── docker-compose.yml
├── .env                       # Variables locales
└── .env.coolify               # Variables produccion
```

## Quick Start

```bash
# Local
cp .env.example .env
# Editar .env con SECRET_KEYs y SUPABASE_URL/SERVICE_KEY/ANON_KEY

docker compose up --build
```

## Variables requeridas

```env
# Supabase (obligatorio para auth sessions)
SUPABASE_URL=https://umzlwcdjxtbdoqiclolo.supabase.co
SUPABASE_SERVICE_KEY=eyJ...
SUPABASE_ANON_KEY=eyJ...

# Secret Keys (una por servicio)
VANITY_HQ_SECRET_KEY=...
VANITY_PAYROLL_SECRET_KEY=...
VANITY_DASHBOARD_SECRET_KEY=...
VANITY_ACTAS_SECRET_KEY=...
VANITY_EMPREQ_SECRET_KEY=...

# HRMgr Django
HRMGR_SECRET_KEY=...
HRMGR_DB_PASSWORD=...
```

## Auth Flow

1. Usuario hace login en HQ Wrapper (`/login`)
2. HQ crea sesion en Supabase (`vanity_sessions`) y emite token SSO
3. El token redirige al microservicio destino (`/auth/hq?token=...`)
4. El microservicio valida el token y crea sesion local (respaldada por Supabase)
5. Logout revoca la sesion en Supabase (efectivo en todos los servicios)

## Deploy en Coolify

1. Configurar variables en `.env.coolify`
2. Ejecutar `vanity_common/supabase_schema.sql` en el SQL Editor de Supabase
3. `docker compose up -d --build`

## Scripts

- `vanity_payroll/scripts/migration/import_fresha_to_supabase.py` — Importar citas de Fresha (solo nuevas con `--dry-run`)
- `vanity_dashboard/supabase_loader.py` — Cargar datos desde Supabase al dashboard