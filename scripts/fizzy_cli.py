#!/usr/bin/env python3
"""Fizzy CLI for Cadrex tasks and activity tracking."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from kadrix.db import get_conn  # noqa: E402


DEFAULT_COLUMNS = (
    ("Propuesto", 0, "#64748b"),
    ("Asignado", 1, "#2563eb"),
    ("In Process", 2, "#d97706"),
    ("Bloqueado", 3, "#dc2626"),
    ("Done", 4, "#16a34a"),
)

ACTIVITY_TYPES = (
    "task_created",
    "task_updated",
    "task_moved",
    "task_completed",
    "comment_added",
    "fixture_maintenance",
    "fixture_status_change",
    "project_created",
    "project_updated",
    "login",
    "other",
)


def db_all(sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    conn = get_conn()
    cur = conn.cursor(dictionary=True)
    cur.execute(sql, params)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def db_exec(sql: str, params: tuple[Any, ...] = ()) -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(sql, params)
    last_id = cur.lastrowid
    conn.commit()
    cur.close()
    conn.close()
    return int(last_id or 0)


def ensure_user(username: str = "fizzy") -> int:
    rows = db_all("SELECT id FROM kadrix_users WHERE username = %s LIMIT 1", (username,))
    if rows:
        return int(rows[0]["id"])
    return db_exec(
        """
        INSERT INTO kadrix_users (username, name, email, role, password_hash)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (username, "Fizzy Agent", f"{username}@cadrex.local", "manager", "cli-managed"),
    )


def ensure_board(name: str = "Produccion y Mantenimiento") -> int:
    rows = db_all("SELECT id FROM kadrix_boards WHERE name = %s LIMIT 1", (name,))
    if rows:
        return int(rows[0]["id"])
    bid = db_exec(
        "INSERT INTO kadrix_boards (name, description) VALUES (%s, %s)",
        (name, "Tablero principal de tareas Cadrex/Fizzy"),
    )
    for col_name, position, color in DEFAULT_COLUMNS:
        db_exec(
            "INSERT INTO kadrix_columns (board_id, name, position, color) VALUES (%s, %s, %s, %s)",
            (bid, col_name, position, color),
        )
    return bid


def find_column(status: str, board_id: int | None = None) -> tuple[int, str, int]:
    board_id = board_id or ensure_board()
    rows = db_all(
        """
        SELECT id, name, board_id
        FROM kadrix_columns
        WHERE board_id = %s AND LOWER(name) = LOWER(%s)
        LIMIT 1
        """,
        (board_id, status),
    )
    if not rows:
        known = db_all("SELECT name FROM kadrix_columns WHERE board_id = %s ORDER BY position", (board_id,))
        names = ", ".join(row["name"] for row in known) or "sin columnas"
        raise SystemExit(f"Status no encontrado: {status}. Disponibles: {names}")
    row = rows[0]
    return int(row["id"]), str(row["name"]), int(row["board_id"])


def log_activity(
    activity_type: str,
    description: str,
    *,
    username: str = "fizzy",
    task_id: int | None = None,
    fixture_id: int | None = None,
    minutes: int | None = None,
) -> int:
    user_id = ensure_user(username)
    return db_exec(
        """
        INSERT INTO kadrix_activities
        (user_id, activity_type, description, related_fixture_id, related_task_id, duration_minutes)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (user_id, activity_type, description, fixture_id, task_id, minutes),
    )


def render_table(rows: list[dict[str, Any]], columns: list[tuple[str, str]], empty: str) -> None:
    if not rows:
        print(empty)
        return
    widths = []
    for key, title in columns:
        values = ["" if row.get(key) is None else str(row.get(key)) for row in rows]
        widths.append(min(max([len(title), *[len(v) for v in values]]), 42))
    print("  ".join(title.ljust(widths[i]) for i, (_, title) in enumerate(columns)))
    print("  ".join("-" * width for width in widths))
    for row in rows:
        cells = []
        for i, (key, _) in enumerate(columns):
            value = "" if row.get(key) is None else str(row.get(key))
            if len(value) > widths[i]:
                value = value[: widths[i] - 3] + "..."
            cells.append(value.ljust(widths[i]))
        print("  ".join(cells))


def cmd_tasks(args: argparse.Namespace) -> None:
    params: list[Any] = []
    where = []
    if args.status:
        where.append("LOWER(c.name) = LOWER(%s)")
        params.append(args.status)
    elif not args.all:
        where.append("c.name != 'Done'")
    if args.assignee:
        where.append("LOWER(COALESCE(u.name, u.username, '')) LIKE LOWER(%s)")
        params.append(f"%{args.assignee}%")
    sql = """
        SELECT t.id, t.title, c.name AS status, t.priority,
               COALESCE(u.name, 'sin asignar') AS assignee,
               COALESCE(DATE_FORMAT(t.due_date, '%Y-%m-%d'), '') AS due_date,
               DATE_FORMAT(t.updated_at, '%Y-%m-%d %H:%i') AS updated
        FROM kadrix_tasks t
        JOIN kadrix_columns c ON t.column_id = c.id
        LEFT JOIN kadrix_users u ON t.assigned_to = u.id
    """
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY FIELD(t.priority, 'critical', 'high', 'medium', 'low'), t.due_date IS NULL, t.due_date ASC, t.updated_at DESC LIMIT %s"
    params.append(args.limit)
    rows = db_all(sql, tuple(params))
    render_table(
        rows,
        [
            ("id", "ID"),
            ("status", "Status"),
            ("priority", "Prioridad"),
            ("assignee", "Responsable"),
            ("due_date", "Vence"),
            ("title", "Task"),
        ],
        "Sin tasks para el filtro.",
    )


def cmd_task_create(args: argparse.Namespace) -> None:
    board_id = ensure_board(args.board)
    column_id, status_name, _ = find_column(args.status, board_id)
    user_id = ensure_user(args.user)
    assignee_id = None
    if args.assignee:
        rows = db_all(
            "SELECT id FROM kadrix_users WHERE LOWER(username)=LOWER(%s) OR LOWER(name)=LOWER(%s) LIMIT 1",
            (args.assignee, args.assignee),
        )
        assignee_id = int(rows[0]["id"]) if rows else None
    task_id = db_exec(
        """
        INSERT INTO kadrix_tasks
        (board_id, column_id, title, description, assigned_to, priority, due_date, created_by)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (board_id, column_id, args.title, args.description or "", assignee_id, args.priority, args.due, user_id),
    )
    log_activity("task_created", f"Fizzy creo task: {args.title}", username=args.user, task_id=task_id)
    print(f"Task #{task_id} creada en {status_name}.")


def cmd_task_move(args: argparse.Namespace) -> None:
    rows = db_all(
        """
        SELECT t.id, t.title, t.board_id
        FROM kadrix_tasks t
        WHERE t.id = %s
        LIMIT 1
        """,
        (args.task_id,),
    )
    if not rows:
        raise SystemExit(f"Task no encontrada: {args.task_id}")
    task = rows[0]
    column_id, status_name, _ = find_column(args.status, int(task["board_id"]))
    db_exec("UPDATE kadrix_tasks SET column_id = %s WHERE id = %s", (column_id, args.task_id))
    log_activity(
        "task_moved",
        f"Fizzy movio {task['title']} a {status_name}",
        username=args.user,
        task_id=args.task_id,
    )
    print(f"Task #{args.task_id} movida a {status_name}.")


def cmd_activity_list(args: argparse.Namespace) -> None:
    rows = db_all(
        """
        SELECT a.id, DATE_FORMAT(a.created_at, '%Y-%m-%d %H:%i') AS created,
               a.activity_type, COALESCE(u.name, u.username) AS user_name,
               COALESCE(a.related_task_id, '') AS task_id,
               COALESCE(a.duration_minutes, '') AS minutes,
               a.description
        FROM kadrix_activities a
        JOIN kadrix_users u ON a.user_id = u.id
        WHERE a.created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)
        ORDER BY a.created_at DESC
        LIMIT %s
        """,
        (args.days, args.limit),
    )
    render_table(
        rows,
        [
            ("created", "Fecha"),
            ("activity_type", "Tipo"),
            ("user_name", "Usuario"),
            ("task_id", "Task"),
            ("minutes", "Min"),
            ("description", "Actividad"),
        ],
        "Sin actividades registradas.",
    )


def cmd_activity_add(args: argparse.Namespace) -> None:
    activity_id = log_activity(
        args.type,
        args.description,
        username=args.user,
        task_id=args.task_id,
        fixture_id=args.fixture_id,
        minutes=args.minutes,
    )
    print(f"Actividad #{activity_id} registrada.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fizzy",
        description="CLI para ver tasks y trackear actividades de Cadrex/Fizzy.",
    )
    parser.add_argument("--user", default=os.getenv("FIZZY_USER", "fizzy"), help="Usuario Fizzy para auditoria.")
    sub = parser.add_subparsers(dest="command", required=True)

    tasks = sub.add_parser("tasks", help="Lista tasks del tablero.")
    tasks.add_argument("--status", help="Filtra por status/columna, ej. 'In Process'.")
    tasks.add_argument("--assignee", help="Filtra por responsable.")
    tasks.add_argument("--all", action="store_true", help="Incluye Done.")
    tasks.add_argument("--limit", type=int, default=50)
    tasks.set_defaults(func=cmd_tasks)

    task_create = sub.add_parser("task-create", help="Crea una task.")
    task_create.add_argument("--title", required=True)
    task_create.add_argument("--description", default="")
    task_create.add_argument("--status", default="Propuesto")
    task_create.add_argument("--priority", choices=("low", "medium", "high", "critical"), default="medium")
    task_create.add_argument("--assignee")
    task_create.add_argument("--due")
    task_create.add_argument("--board", default="Produccion y Mantenimiento")
    task_create.set_defaults(func=cmd_task_create)

    task_move = sub.add_parser("task-move", help="Mueve una task a otro status.")
    task_move.add_argument("task_id", type=int)
    task_move.add_argument("--status", required=True)
    task_move.set_defaults(func=cmd_task_move)

    activity = sub.add_parser("activity", help="Lista actividades.")
    activity.add_argument("--days", type=int, default=7)
    activity.add_argument("--limit", type=int, default=50)
    activity.set_defaults(func=cmd_activity_list)

    activity_add = sub.add_parser("activity-add", help="Registra actividad.")
    activity_add.add_argument("description")
    activity_add.add_argument("--type", choices=ACTIVITY_TYPES, default="other")
    activity_add.add_argument("--minutes", type=int)
    activity_add.add_argument("--task-id", type=int)
    activity_add.add_argument("--fixture-id", type=int)
    activity_add.set_defaults(func=cmd_activity_add)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.func(args)
    except Exception as exc:
        if "1146" in str(exc) and "kadrix_" in str(exc):
            print(
                "Error Fizzy CLI: faltan tablas kadrix_* en MySQL. "
                "Aplica adriana_projects/mysql/init/02_kadrix_schema.sql antes de usar Fizzy.",
                file=sys.stderr,
            )
            return 1
        print(f"Error Fizzy CLI: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
