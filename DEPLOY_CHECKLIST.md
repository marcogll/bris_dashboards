# Deploy Checklist - Vanity HQ

## Pre-Deploy (Local)

- [ ] Copiar `.env.example` a `.env` y llenar todos los valores
  ```bash
  cp .env.example .env
  # Generar secret keys:
  # for key in VANITY_HQ_SECRET_KEY VANITY_PAYROLL_SECRET_KEY VANITY_DASHBOARD_SECRET_KEY VANITY_ACTAS_SECRET_KEY VANITY_EMPREQ_SECRET_KEY HRMGR_SECRET_KEY; do
  #   echo "$key=$(openssl rand -hex 32)"
  # done
  # Llenar SUPABASE_URL, SUPABASE_SERVICE_KEY, SUPABASE_ANON_KEY
  # Llenar HRMGR_DB_PASSWORD
  ```
- [ ] Ejecutar schema en Supabase: `vanity_common/supabase_schema.sql` en SQL Editor
- [ ] Verificar migraciones generadas:
  ```bash
  ls vanity_hrmgr/employees/migrations/0001_initial.py
  ```
- [ ] Build y levantar servicios:
  ```bash
  docker compose up --build
  ```
- [ ] Verificar que todos los servicios esten healthy:
  ```bash
  docker compose ps
  ```
- [ ] Ejecutar test de deploy:
  ```bash
  bash scripts/test_deploy.sh local
  ```

## Deploy en VPS

- [ ] Configurar VPS (Ubuntu 22.04+):
  ```bash
  sudo apt update && sudo apt upgrade -y
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker $USER
  ```
- [ ] Clonar repositorio en VPS
- [ ] Generar `.env` de produccion:
  ```bash
  bash scripts/setup_env_secrets.sh
  cp .env.production .env
  # Editar .env con SUPABASE_URL/SERVICE_KEY/ANON_KEY
  ```
- [ ] Verificar schema en Supabase (si no existe)
- [ ] Levantar servicios:
  ```bash
  docker compose up -d --build
  ```
- [ ] Verificar salud de todos los servicios:
  ```bash
  docker compose ps
  docker compose logs -f --tail=50
  ```
- [ ] Ejecutar test de deploy remoto:
  ```bash
  bash scripts/test_deploy.sh remote
  ```

## Post-Deploy

- [ ] Cambiar password del usuario admin seed (`admin@vanity.local` / `VanityAdmin2026!`)
- [ ] Verificar SSL/TLS si se usa reverse proxy
- [ ] Configurar backups de volumenes Docker
- [ ] Rotar secret keys si `.env.coolify` fue expuesto en git

## Puertos de Servicio

| Servicio | Puerto | Healthcheck |
|----------|--------|-------------|
| HQ Wrapper | 5050 | /healthz |
| Dashboard | 5002 | /healthz |
| Payroll | 5051 | /healthz |
| HRMgr Web | 8000 | /healthz |
| HRMgr Celery | - | celery inspect ping |
| Actas | 5052 | /healthz |
| EmpReq | 5053 | /healthz |
| PostgreSQL | 5432 | pg_isready |
| Redis | 6379 | redis-cli ping |

## Troubleshooting

- **hrmgr-web no inicia**: Verificar que Postgres este healthy y las migraciones corrieron (`docker compose logs hrmgr-web`)
- **SSO falla**: Verificar `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `SUPABASE_ANON_KEY` en `.env`
- **Datos se pierden**: Verificar que `actas_data`, `empreq_data`, `hq_wrapper_data`, `payroll_data`, `postgres_data` esten en `docker volume ls`