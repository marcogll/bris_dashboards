"""Cadrix — Natural Language Task Creation via OpenRouter."""
import json
import logging
import os
from datetime import date, datetime, timedelta

import requests

from kadrix.db import execute, query

logger = logging.getLogger("bris_dashboard.nl_tasks")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "anthropic/claude-3-haiku")


def _call_openrouter_structured(system: str, user_msg: str) -> dict:
    if not OPENROUTER_API_KEY:
        return {"error": "OpenRouter no configurado"}
    try:
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "HTTP-Referer": "https://soul23.mx",
                "X-Title": "Cadrex NL Task Extractor",
            },
            json={
                "model": OPENROUTER_MODEL,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_msg},
                ],
                "max_tokens": 500,
                "temperature": 0.3,
                "response_format": {"type": "json_object"},
            },
            timeout=20,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        return json.loads(content)
    except Exception as exc:
        logger.warning("NL extraction error: %s", exc)
        return {"error": str(exc)}


def _resolve_user(username_hint: str) -> dict | None:
    username_hint = username_hint.strip().lower().lstrip("@") if username_hint else ""
    if not username_hint:
        return None
    rows = query(
        "SELECT id, name, username FROM kadrix_users WHERE username = %s AND active = 1",
        (username_hint,),
    )
    if rows:
        return rows[0]
    # fuzzy match by name
    rows = query(
        "SELECT id, name, username FROM kadrix_users WHERE name LIKE %s AND active = 1 LIMIT 1",
        (f"%{username_hint}%",),
    )
    return rows[0] if rows else None


def _resolve_column(board_id: int, col_hint: str | None) -> int | None:
    if not col_hint:
        rows = query(
            "SELECT id FROM kadrix_columns WHERE board_id = %s ORDER BY position LIMIT 1",
            (board_id,),
        )
        return rows[0]["id"] if rows else None
    rows = query(
        "SELECT id FROM kadrix_columns WHERE board_id = %s AND name LIKE %s LIMIT 1",
        (board_id, f"%{col_hint}%"),
    )
    if rows:
        return rows[0]["id"]
    rows = query(
        "SELECT id FROM kadrix_columns WHERE board_id = %s ORDER BY position LIMIT 1",
        (board_id,),
    )
    return rows[0]["id"] if rows else None


def _resolve_date(date_hint: str | None) -> str | None:
    if not date_hint:
        return None
    dh = date_hint.strip().lower()
    today = date.today()
    if dh in ("hoy", "today"):
        return today.isoformat()
    if dh in ("mañana", "manana", "tomorrow"):
        return (today + timedelta(days=1)).isoformat()
    if dh in ("pasado mañana", "pasado manana"):
        return (today + timedelta(days=2)).isoformat()
    # Try ISO
    try:
        return datetime.strptime(dh, "%Y-%m-%d").date().isoformat()
    except ValueError:
        pass
    # Try common formats
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y", "%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(dh, fmt).date().isoformat()
        except ValueError:
            pass
    return None


def _build_system_prompt() -> str:
    users = query("SELECT username, name FROM kadrix_users WHERE active = 1 LIMIT 50")
    user_list = ", ".join([f"{u['username']} ({u['name']})" for u in users]) if users else "adriana"
    return (
        "Eres un extractor de datos para el sistema Cadrex. "
        "El usuario describe una tarea en lenguaje natural. "
        "Extrae los campos y devuelve ÚNICAMENTE un JSON válido con esta estructura:\n"
        "{\n"
        '  "title": string obligatorio,\n'
        '  "description": string opcional,\n'
        '  "assigned_to_username": string opcional (username del usuario),\n'
        '  "priority": "low" | "medium" | "high" | "critical", default "medium",\n'
        '  "due_date_hint": string opcional (ej: "mañana", "2026-05-30", "hoy"),\n'
        '  "column_hint": string opcional (ej: "Backlog", "In Progress"), default "Backlog",\n'
        '  "board_id": int opcional, default 1\n'
        "}\n\n"
        f"Usuarios disponibles: {user_list}\n"
        "Si falta información crítica (título), devuelve: {\"error\": \"falta_titulo\"}\n"
        "Responde SOLO con el JSON, sin markdown, sin explicaciones."
    )


def create_task_from_text(text: str, from_user: dict) -> dict:
    """Parse NL text into a kadrix_tasks row. Returns {"ok": bool, "message": str, "task_id": int|None}."""
    system = _build_system_prompt()
    parsed = _call_openrouter_structured(system, text)

    if parsed.get("error"):
        return {"ok": False, "message": f"❌ No entendí bien: {parsed['error']}", "task_id": None}

    title = (parsed.get("title") or "").strip()
    if not title:
        return {"ok": False, "message": "❌ Necesito que me des un título para la tarea.", "task_id": None}

    # Resolve assigned_to
    assigned_hint = (parsed.get("assigned_to_username") or "").strip().lower()
    assigned_to = None
    if assigned_hint:
        u = _resolve_user(assigned_hint)
        if u:
            assigned_to = u["id"]
        else:
            return {"ok": False, "message": f"❌ No encontré al usuario '*{assigned_hint}*'.", "task_id": None}
    else:
        assigned_to = from_user.get("id")

    board_id = int(parsed.get("board_id") or 1)
    col_hint = (parsed.get("column_hint") or "Backlog").strip()
    column_id = _resolve_column(board_id, col_hint)
    if not column_id:
        return {"ok": False, "message": "❌ No se encontró un tablero válido.", "task_id": None}

    priority = (parsed.get("priority") or "medium").lower()
    if priority not in ("low", "medium", "high", "critical"):
        priority = "medium"

    due_date = _resolve_date(parsed.get("due_date_hint"))
    description = (parsed.get("description") or "").strip()

    task_id = execute(
        """
        INSERT INTO kadrix_tasks
        (board_id, column_id, title, description, assigned_to, priority, due_date, created_by)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (board_id, column_id, title, description, assigned_to, priority, due_date, from_user.get("id")),
    )

    if not task_id:
        return {"ok": False, "message": "❌ Error al guardar la tarea en la base de datos.", "task_id": None}

    assignee_name = from_user.get("name", "ti")
    if assigned_to and assigned_to != from_user.get("id"):
        u = query("SELECT name FROM kadrix_users WHERE id = %s", (assigned_to,))
        if u:
            assignee_name = u[0]["name"]

    due_str = f", vence *{due_date}*" if due_date else ""
    msg = (
        f"✅ *Tarea #{task_id} creada*\n"
        f"• *{title}*\n"
        f"• Asignada a: {assignee_name}\n"
        f"• Prioridad: {priority}{due_str}"
    )
    return {"ok": True, "message": msg, "task_id": task_id}
