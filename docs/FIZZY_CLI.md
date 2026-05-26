# Fizzy CLI

Comandos para consultar tasks y registrar actividades de Cadrex/Fizzy desde terminal.

## Uso

```bash
python3 scripts/fizzy_cli.py tasks
python3 scripts/fizzy_cli.py tasks --status "In Process"
python3 scripts/fizzy_cli.py tasks --all --limit 100

python3 scripts/fizzy_cli.py task-create --title "Revisar fixture gaskets" --status "Asignado" --priority high --due 2026-05-28
python3 scripts/fizzy_cli.py task-move 12 --status "Done"

python3 scripts/fizzy_cli.py activity
python3 scripts/fizzy_cli.py activity --days 14
python3 scripts/fizzy_cli.py activity-add "Se reviso avance del fixture de gaskets" --type other --minutes 25 --task-id 12
```

## Variables

La CLI usa las mismas variables MySQL de la app:

```bash
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=bris_user
MYSQL_PASSWORD=...
MYSQL_DATABASE=bris_adriana
```

Para auditar con otro usuario:

```bash
python3 scripts/fizzy_cli.py --user marco activity-add "Revision diaria del board"
```
