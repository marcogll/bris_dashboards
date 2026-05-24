<p align="center">
  <img src="https://raw.githubusercontent.com/marcogll/mg_data_storage/refs/heads/main/soul23/logo/soul23_logo.svg" width="110" alt="BRIS Rack Assembly Dashboard">
</p>

<h1 align="center">BRIS Rack Assembly Dashboard</h1>

<p align="center">
  Sistema operativo para KPIs de ensamble, analisis de proyectos y carga estructurada de datos en MySQL.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3a3a3a?style=flat-square&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Flask-3a3a3a?style=flat-square&logo=flask&logoColor=white" alt="Flask">
  <img src="https://img.shields.io/badge/MySQL-3a3a3a?style=flat-square&logo=mysql&logoColor=white" alt="MySQL">
  <img src="https://img.shields.io/badge/Docker-3a3a3a?style=flat-square&logo=docker&logoColor=white" alt="Docker">
  <img src="https://img.shields.io/badge/Docker_Compose-3a3a3a?style=flat-square&logo=docker&logoColor=white" alt="Docker Compose">
  <img src="https://img.shields.io/badge/CSV-3a3a3a?style=flat-square&logo=files&logoColor=white" alt="CSV">
  <img src="https://img.shields.io/badge/Coolify-3a3a3a?style=flat-square&logo=coolify&logoColor=white" alt="Coolify">
</p>

---

## Proposito

Este repositorio contiene dos capas de trabajo:

- Dashboard Flask para visualizar KPIs de ensamble desde `data/stations.csv`.
- Pipeline de datos para proyectos de Adriana, con extraccion desde Excel, normalizacion a CSV y carga a MySQL.

El objetivo es que la informacion de proyectos, materiales, BOM, PFEP, work centers, estaciones y kanban quede consultable en una base MySQL, sin depender directamente de hojas Excel para analisis diario.

## Estructura

```text
.
├── app.py
├── docker-compose.yml
├── Dockerfile
├── data/
│   └── stations.csv
├── templates/
│   └── dashboard.html
├── adriana_projects/
│   ├── data/
│   │   ├── raw_csv/
│   │   ├── curated/
│   │   └── summary.json
│   ├── mysql/
│   │   └── init/01_schema.sql
│   └── scripts/
│       ├── build_adriana_dataset.py
│       └── load_mysql.py
└── *.xlsx / *.xlsm
```

## Dashboard de ensamble

El dashboard principal lee `data/stations.csv`.

Columnas requeridas:

```csv
station_id,station_name,time_seconds,operators,observations,action
```

Con esa informacion calcula:

- cuello de botella
- capacidad por hora por estacion
- piezas estimadas por turno
- gap contra takt
- contenido total de trabajo
- rebalanceo sugerido moviendo un operador

Variables relacionadas:

- `DATA_FILE`: ruta del CSV activo dentro del contenedor.
- `AVAILABLE_SECONDS`: segundos disponibles por turno.
- `TAKT_SECONDS`: takt configurado.
- `UPLOAD_SECRET`: clave opcional para permitir actualizacion del CSV desde la UI.

## Data de proyectos Adriana

Los archivos Excel del folder raiz se procesan con:

```bash
python3 adriana_projects/scripts/build_adriana_dataset.py
```

El script genera:

- `adriana_projects/data/raw_csv/`: una exportacion CSV por cada hoja detectada.
- `adriana_projects/data/curated/`: datasets normalizados para MySQL.
- `adriana_projects/data/summary.json`: conteo de registros generados.

Resumen actual de la extraccion:

```json
{
  "source_sheets": 35,
  "raw_rows": 3938,
  "parts": 416,
  "bom_items": 546,
  "pfep_items": 336,
  "work_center_operations": 430,
  "station_materials": 52,
  "kanban_notifications": 2
}
```

## Datasets curados

Los CSV curados son la entrada directa a MySQL:

- `source_sheets.csv`: inventario de archivos y hojas procesadas.
- `raw_rows.csv`: respaldo raw de cada fila como JSON.
- `parts.csv`: catalogo consolidado de numeros de parte.
- `bom_items.csv`: relaciones BOM, inventario, proveedores y lead times.
- `pfep_items.csv`: plan for every part, rutas, estaciones, carts, bins y cantidades.
- `work_center_operations.csv`: operaciones por work center, standard rate y crew size.
- `station_materials.csv`: materiales por estacion, paso, rack, tooling y notas.
- `kanban_notifications.csv`: alertas kanban con dias restantes y owner.

## Modelo MySQL

El schema se inicializa desde:

```text
adriana_projects/mysql/init/01_schema.sql
```

Tablas principales:

- `source_sheets`
- `raw_rows`
- `parts`
- `bom_items`
- `pfep_items`
- `work_center_operations`
- `station_materials`
- `kanban_notifications`

Vistas de analisis:

- `v_material_shortages`: materiales con riesgo por disponibilidad o lead time alto.
- `v_station_load`: carga por estacion y cantidad de partes.
- `v_work_center_bottlenecks`: work centers ordenados por carga de standard rate.

## Local sin Docker

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python app.py
```

Abrir:

```text
http://localhost:5000
```

Si el puerto 5000 esta ocupado:

```bash
PORT=5001 .venv/bin/python app.py
```

## Docker Compose

Crear variables locales:

```bash
cp .env.example .env
```

Levantar dashboard y MySQL:

```bash
docker compose up --build
```

Levantar solo MySQL:

```bash
docker compose up -d mysql
```

Regenerar los CSV curados:

```bash
python3 adriana_projects/scripts/build_adriana_dataset.py
```

Cargar MySQL con los CSV curados:

```bash
docker compose --profile import run --rm adriana-importer
```

La carga trunca y recarga las tablas administradas por el pipeline para mantener consistencia con los CSV actuales.

## Variables

Variables esperadas en `.env` o en Coolify:

```env
APP_TITLE=BRIS Rack Assembly Dashboard
DATA_FILE=/app/data/stations.csv
AVAILABLE_SECONDS=39900
TAKT_SECONDS=2216.666667
PORT=5000
SECRET_KEY=change-me
UPLOAD_SECRET=
MYSQL_DATABASE=bris_adriana
MYSQL_USER=bris_user
MYSQL_PASSWORD=change-me
MYSQL_ROOT_PASSWORD=change-root-password
MYSQL_PORT=3306
```

## Consultas utiles

Materiales con riesgo:

```sql
SELECT *
FROM v_material_shortages
ORDER BY max_lead_time_days DESC, min_available ASC;
```

Carga por estacion:

```sql
SELECT *
FROM v_station_load
ORDER BY total_pieces DESC;
```

Work centers con mayor carga:

```sql
SELECT *
FROM v_work_center_bottlenecks
LIMIT 20;
```

Partes por estacion:

```sql
SELECT station_name, part_number, units, total_pieces
FROM station_materials
WHERE part_number IS NOT NULL
ORDER BY station_name, step;
```

## Coolify

Usar `docker-compose.yml` como Docker Compose file.

Configuracion recomendada:

- Definir las variables de `.env.example` en el panel de Coolify.
- Mantener el volumen `mysql-data` para persistencia de MySQL.
- Ejecutar el servicio principal `bris-dashboard`.
- Ejecutar el perfil `import` cuando se quiera recargar MySQL desde los CSV curados.

Para actualizar informacion:

1. Subir o reemplazar Excel en el repositorio.
2. Ejecutar `python3 adriana_projects/scripts/build_adriana_dataset.py`.
3. Commit de los CSV generados.
4. Deploy en Coolify.
5. Ejecutar `adriana-importer` para refrescar MySQL.

## Flujo operativo

1. Excel nuevo entra al folder raiz.
2. El extractor genera raw CSV y datasets curados.
3. MySQL guarda la informacion estructurada.
4. Las vistas permiten revisar riesgos de materiales, carga de estaciones y work centers.
5. El dashboard sigue disponible para KPIs rapidos de ensamble desde CSV.

## Integracion Multiagente (Vanity Ecosystem)

BRIS Dashboard puede operar como un agente mas dentro del ecosistema Vanity.

### Caracteristicas de compatibilidad

- **ProxyFix**: soporta reverse proxy (Traefik/Nginx) via `werkzeug.middleware.proxy_fix`
- **Healthcheck**: endpoint `/healthz` compatible con el patron de servicios Vanity
- **Puerto dinamico**: configurable via variable `PORT`

### Registro en HQ Wrapper

Agregar a `SYSTEMS` en `vanity_hq_wrapper/app.py`:

```python
"bris_dashboard": {
    "name": "BRIS Dashboard",
    "description": "KPIs de ensamble, balanceo de lineas, BOM y kanban.",
    "url": os.getenv("VANITY_BRIS_PUBLIC_URL", "http://bris-dashboard:5004"),
    "modules": ["production", "plan", "parts", "kanban", "reports"],
}
```

### Docker Compose con Vanity

Usar `docker-compose.vanity.yml`:

```bash
docker compose -f docker-compose.vanity.yml up -d
```

Requiere que la red `vanity-network` ya exista (creada por el compose principal de Vanity).

## Notas de mantenimiento

- Los Excel originales se conservan como fuentes.
- `raw_rows` permite auditoria cuando una hoja no tiene estructura limpia.
- Las tablas curadas son para analisis y consultas operativas.
- Si cambia el formato de una hoja, ajustar `build_adriana_dataset.py` y regenerar.
