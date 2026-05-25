# Cadrex / BRIS Dashboard

Dashboard de producción y gestión de operaciones para Cadrex (Adriana Ramos).

## Stack

- **Backend**: Flask 3.0.3 + Gunicorn
- **Frontend**: Jinja2 + CSS custom
- **Base de datos**: MySQL 8.4
- **Chatbot**: OpenRouter (Claude 3 Haiku)
- **Kanban/Proyectos**: Sistema propio Kadrix

## Estructura

```
.
├── app.py                    # Flask app principal
├── docker-compose.yml        # MySQL + Cadrex
├── Dockerfile                # Build de la app
├── kadrix/                   # Blueprint Kanban/Proyectos/Fixtures
│   ├── __init__.py
│   ├── views.py
│   ├── db.py
│   ├── analytics.py
│   └── telegram_bot.py
├── templates/
│   ├── base.html
│   ├── login.html
│   ├── dashboard.html
│   ├── dashboard_master.html
│   ├── datos.html
│   ├── plan.html
│   ├── produccion.html
│   ├── kanban.html
│   ├── reporte_ejecutivo_15k.html
│   └── kadrix/              # Templates del sistema Kadrix
├── static/css/
│   └── dashboard.css
├── data/
│   ├── stations.csv         # Datos de estaciones de ensamble
│   └── fallbacks/           # Datos fallback CSV/JSON
├── adriana_projects/
│   └── mysql/init/          # Schemas SQL (01-05)
└── scripts/
    └── seed_users.py        # Seed de usuarios
```

## Variables de entorno

```bash
SECRET_KEY=...
MYSQL_HOST=mysql
MYSQL_USER=bris_user
MYSQL_PASSWORD=...
MYSQL_DATABASE=bris_adriana
OPENROUTER_API_KEY=sk-or-v1-...
TELEGRAM_BOT_TOKEN=...
TELEGRAM_WEBHOOK_URL=https://abr.soul23.cloud/api/telegram/webhook
```

## Deploy

Coolify v4 + Docker Compose. El compose levanta MySQL 8.4 con auto-inicialización de schemas y la app Flask en puerto 8743.

```bash
git push origin main
# Luego Deploy en Coolify UI
```
