# Infraestructura — Cadrex

## Visión General

El despliegue se basa en contenedores Docker, orquestados mediante Docker Compose y gestionados en producción por **Coolify** con **Traefik** como reverse proxy y terminador SSL.

El stack principal (`docker-compose.yml`) levanta BRIS Dashboard como servicio único con healthcheck, preparado para integrarse en la red externa `coolify` que gestiona Traefik.

MySQL puede operar como servicio adicional en el mismo compose o como base de datos externa gestionada por Coolify.

---

## Redes Docker

| Red | Tipo | Uso |
|-----|------|-----|
| `coolify` | Externa | Conexión con Traefik/Coolify para SSL y routing |

La red se crea externamente para permitir que Coolify gestione el routing sin modificar el compose de la aplicación.

```bash
# Creada automáticamente por Coolify
docker network create coolify
```

---

## Servicios Docker

### BRIS Dashboard

```yaml
# docker-compose.yml
services:
  dashboard:
    build: .
    container_name: bris-dashboard
    volumes:
      - ./data:/app/data
      - ./claude:/app/claude
    environment:
      - PORT=${PORT:-8743}
      - SECRET_KEY=${SECRET_KEY:?required}
      - FLASK_ENV=${FLASK_ENV:-production}
      - MYSQL_HOST=${MYSQL_HOST:-mysql}
      - MYSQL_PORT=${MYSQL_PORT:-3306}
      - MYSQL_USER=${MYSQL_USER:-bris_user}
      - MYSQL_PASSWORD=${MYSQL_PASSWORD:?required}
      - MYSQL_DATABASE=${MYSQL_DATABASE:-bris_adriana}
      - UPLOAD_SECRET=${UPLOAD_SECRET:-}
      - APP_TITLE=${APP_TITLE:-Cadrex — Dashboard}
      - AVAILABLE_SECONDS=${AVAILABLE_SECONDS:-39900}
      - TAKT_SECONDS=${TAKT_SECONDS:-2216.666667}
      - DATA_FILE=${DATA_FILE:-/app/data/stations.csv}
    expose:
      - "8743"
    labels:
      - "traefik.docker.network=coolify"
      - "traefik.http.services.dashboard.loadbalancer.server.port=8743"
    restart: unless-stopped
    networks:
      - coolify
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8743/healthz')"]
      interval: 30s
      timeout: 10s
      retries: 3
```

**Notas**:
- No expone puertos host directamente; usa `expose` para que solo Traefik/Coolify acceda.
- Labels de Traefik permiten routing por dominio/path sin exponer el puerto.
- Healthcheck interno vía Python `urllib` a `/healthz`.

### MySQL (Opcional)

Si se requiere MySQL para el pipeline Adriana dentro del mismo compose:

```yaml
  mysql:
    image: mysql:8.4
    container_name: cadrex-mysql
    env_file: [.env]
    environment:
      MYSQL_DATABASE: ${MYSQL_DATABASE:-bris_adriana}
      MYSQL_USER: ${MYSQL_USER:-bris_user}
      MYSQL_PASSWORD: ${MYSQL_PASSWORD:-bris_password}
      MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD:-bris_root_password}
    expose: ["3306"]
    volumes:
      - cadrex_mysql_data:/var/lib/mysql
      - ./adriana_projects/mysql/init:/docker-entrypoint-initdb.d:ro
    networks: [coolify]
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "127.0.0.1", "-u", "root", "-p${MYSQL_ROOT_PASSWORD}"]
      interval: 20s
      timeout: 5s
      retries: 10
      start_period: 30s

  adriana-importer:
    build: .
    profiles: [import]
    env_file: [.env]
    environment:
      MYSQL_HOST: mysql
      MYSQL_PORT: 3306
    depends_on: [mysql]
    command: ["python", "adriana_projects/scripts/load_mysql.py"]
    networks: [coolify]
```

---

## Dockerfile

```dockerfile
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PORT=8743
EXPOSE 8743
CMD gunicorn --bind 0.0.0.0:${PORT} --workers 4 --timeout 30 --access-logfile - --error-logfile - app:app
```

**Decisiones**:
- `python:3.12-slim` para balance entre tamaño y compatibilidad.
- `PYTHONDONTWRITEBYTECODE=1` evita `.pyc` en contenedores efímeros.
- Gunicorn con 4 workers y timeout 30s.
- `COPY . .` copia todo el contexto incluyendo `templates/`, `static/`, `data/`.

---

## Coolify — Configuración Recomendada

### Variables de Entorno

Definir en el panel de Coolify (o en `.env`):

| Variable | Valor ejemplo | Requerido |
|----------|---------------|-----------|
| `PORT` | `8743` | Sí |
| `SECRET_KEY` | `openssl rand -hex 32` | Sí |
| `FLASK_ENV` | `production` | Sí |
| `MYSQL_HOST` | `mysql` (o host externo) | Si usa MySQL |
| `MYSQL_PASSWORD` | (secret) | Sí |
| `UPLOAD_SECRET` | (secret opcional) | No |
| `LOGIN_REQUIRED` | `false` | No |
| `OPENROUTER_API_KEY` | `sk-or-v1-...` | No |

### Volumenes

- `./data:/app/data` — persistencia de CSVs y `users.json`
- `cadrex_mysql_data:/var/lib/mysql` — persistencia de base de datos (si MySQL está en compose)

### Healthchecks

Coolify utiliza el healthcheck definido en `docker-compose.yml` para determinar si el contenedor está sano. El endpoint `/healthz` responde `200 OK` inmediatamente.

### SSL / Dominios

- Coolify + Traefik manejan SSL automáticamente vía Let's Encrypt.
- El dominio se configura en el recurso de Coolify; no requiere Nginx manual.
- Para sub-rutas (ej. `cadrex.soul23.cloud/dashboard`), usar path-based routing en Traefik labels.

---

## Scripts de Soporte

### `scripts/setup_env_secrets.sh`

Genera secret keys seguros:

```bash
./scripts/setup_env_secrets.sh
```

Crea/actualiza `.env` con valores `openssl rand -hex 32` para `SECRET_KEY`.

### `scripts/test_deploy.sh`

Valida el despliegue post-deploy:

```bash
# Remoto (producción)
bash scripts/test_deploy.sh remote

# Local (desarrollo)
bash scripts/test_deploy.sh local
```

Verifica:
- Resolución DNS
- Healthchecks (`/healthz`)
- Certificados SSL
- Páginas de login
- Rutas path-based

---

## Flujo de Actualización en Producción

1. **Datos**: Subir/reemplazar Excel en `data/raw/`.
2. **ETL**: Ejecutar `python3 adriana_projects/scripts/build_adriana_dataset.py`.
3. **Commit**: Incluir CSVs generados en `adriana_projects/data/curated/`.
4. **Deploy**: Push trigger en Coolify (o deploy manual).
5. **Import**: Ejecutar perfil `import` para refrescar MySQL:
   ```bash
   docker compose --profile import run --rm adriana-importer
   ```

---

## Puertos y Endpoints Clave

| Servicio | Puerto Interno | Endpoint Público | Healthcheck |
|----------|---------------|------------------|-------------|
| BRIS Dashboard | 8743 | `https://cadrex.soul23.cloud` | `/healthz` |
| MySQL | 3306 | (interno) | `mysqladmin ping` |

---

## Diagrama de Red

```text
Internet
   │
   ▼
[Cloudflare / DNS]
   │
   ▼
[Coolify VPS]
   ├─ Traefik (443 → internal routing)
   │   └─ /cadrex  → bris-dashboard:8743
   │
   └─ coolify network (bridge)
       ├─ bris-dashboard
       └─ cadrex-mysql (opcional)
```
