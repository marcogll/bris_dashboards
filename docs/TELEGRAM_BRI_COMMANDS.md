# Telegram + Bri Command Contract

Este documento define los comandos que debe soportar el bot de Telegram para consultar Cadrex HQ, enviar datos operativos y preguntarle a Bri.

## Conceptos

- **Fizzy**: alias operativo para fixtures. Se usa para reportar estado, mantenimiento y actividades.
- **Boards**: representan proyectos o frentes de trabajo. Las columnas son estados de avance.
- **Responsables**: se asignan con `resp=` o `@usuario`.
- **Tags**: texto libre para clasificar a discrecion, por ejemplo `qa`, `fixture`, `linea-nf`, `urgente`, `tarde`.
- **Turno tarde**: vista filtrada por datos etiquetados como `tarde` o cargados con `turno=tarde`.

## Estados Recomendados

### Fizzy / Fixtures

- `active`: operativo
- `in_process`: en proceso
- `maintenance`: en mantenimiento
- `blocked`: bloqueado
- `inactive`: danado
- `retired`: retirado

### Actividades

- `scheduled`: programada
- `in_process`: en proceso
- `completed`: completada
- `on_hold`: pausada
- `cancelled`: cancelada

### Boards / Proyectos

- `draft`: borrador
- `active`: activo
- `in_process`: en proceso
- `on_hold`: pausado
- `completed`: completado
- `cancelled`: cancelado

## Comandos Telegram

### Ayuda

```text
/start
/help
/modelo
```

- `/start`: inicia el bot y muestra acciones principales.
- `/help`: lista comandos y ejemplos.
- `/modelo`: muestra el modelo de Bri configurado en `OPENROUTER_MODEL`.

### Dashboard

```text
/dashboard
/kpis
/tarde
/linea NORTHFACE
/linea SANMINA
/cuellos
```

- `/dashboard`: resumen ejecutivo del dashboard actual.
- `/kpis`: KPIs clave: pzas/turno, takt, gap, utilizacion, cuellos y avance de plan.
- `/tarde`: resumen de turno tarde.
- `/linea <linea>`: detalle por linea.
- `/cuellos`: estaciones sobre takt o en riesgo.

### Inventario y Fixtures

```text
/kanban
/fixtures
/fizzy status
/fizzy FX-001
```

- `/kanban`: partes criticas, advertencias y OK.
- `/fixtures`: conteo de operativos, mantenimiento, danados y retirados.
- `/fizzy status`: resumen de estados de fixtures.
- `/fizzy <codigo>`: detalle de un fixture.

### Proyectos y Equipo

```text
/proyectos
/proyecto ProyectoA
/equipo
/responsable Marco
```

- `/proyectos`: boards/proyectos activos, pausados y completados.
- `/proyecto <nombre>`: tareas, responsables y estado.
- `/equipo`: responsables activos.
- `/responsable <nombre>`: carga de trabajo por persona.

### Enviar Data

```text
/actividad fixture=FX-001 status=in_process resp=Marco tag=qa nota=Revision de clamps
/actividad proyecto=ShadowBoard status=completed resp=IE tag=tarde nota=Instalado en Est4
/dato linea=NORTHFACE estacion=EST-4 ct=3953 turno=tarde nota=Validacion manual
/fizzy_update fixture=FX-001 status=maintenance resp=Mant tag=urgente nota=Clamp flojo
```

Reglas:

- `nota=` debe ser texto corto.
- `status=` debe usar estados permitidos.
- `tag=` es libre y opcional.
- `turno=tarde` alimenta el dashboard de tarde.
- El bot debe confirmar lo que guardo antes de escribir cuando falte `fixture`, `linea`, `status` o `nota`.

### Preguntar a Bri

```text
/bri que patron ves en Northface?
/bri que fixture esta generando mas riesgo?
/bri compara turno tarde vs dashboard actual
/bri que debo priorizar manana?
```

Bri debe usar el contexto endurecido del dashboard y rechazar instrucciones que intenten cambiar su rol, revelar secretos o salirse de los datos disponibles.

## Endpoint Disponible

La app expone el catalogo en:

```text
GET /api/telegram/commands
```

Ese endpoint devuelve:

- `commands`: lista estructurada para UI/bot.
- `botfather`: lineas listas para configurar comandos en Telegram BotFather.
- `notes`: proveedor, modelo IA y nota de seguridad.

## Webhook Telegram

La app recibe updates de Telegram en:

```text
POST /api/telegram/webhook/<TELEGRAM_WEBHOOK_SECRET>
```

Si el proxy publica la app bajo `/cadrex`, usa:

```text
POST /cadrex/api/telegram/webhook/<TELEGRAM_WEBHOOK_SECRET>
```

Para registrar el webhook en Telegram:

```bash
curl "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/setWebhook?url=https://abr.soul23.cloud/api/telegram/webhook/$TELEGRAM_WEBHOOK_SECRET"
```

Si `https://abr.soul23.cloud/` redirige todo a `/cadrex/`, usa:

```bash
curl "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/setWebhook?url=https://abr.soul23.cloud/cadrex/api/telegram/webhook/$TELEGRAM_WEBHOOK_SECRET"
```

## Variables de Entorno Sugeridas

```text
TELEGRAM_BOT_TOKEN=
TELEGRAM_WEBHOOK_SECRET=
TELEGRAM_ALLOWED_CHAT_IDS=
TELEGRAM_DEFAULT_USER=bris
```

El webhook del bot debe validar `TELEGRAM_WEBHOOK_SECRET` antes de guardar actividades o datos.
