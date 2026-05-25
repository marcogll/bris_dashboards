"""Cadrex — Telegram Bot (Bri)
Lightweight HTTP client using requests (already a project dep).
"""
import json
import logging
import os
from typing import Any

import requests

from kadrix.db import execute, query

logger = logging.getLogger("bris_dashboard.telegram")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_API_BASE = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
TELEGRAM_ADMIN_ID = os.getenv("TELEGRAM_ADMIN_ID", "")


def _api(method: str, payload: dict | None = None) -> dict:
    if not TELEGRAM_BOT_TOKEN:
        logger.warning("TELEGRAM_BOT_TOKEN not set")
        return {"ok": False, "description": "No token"}
    url = f"{TELEGRAM_API_BASE}/{method}"
    try:
        resp = requests.post(url, json=payload or {}, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.warning("Telegram API error (%s): %s", method, exc)
        return {"ok": False, "description": str(exc)}


def send_message(chat_id: int | str, text: str, parse_mode: str = "Markdown") -> dict:
    if len(text) > 4096:
        text = text[:4093] + "..."
    return _api("sendMessage", {"chat_id": chat_id, "text": text, "parse_mode": parse_mode})


def set_webhook(url: str) -> dict:
    return _api("setWebhook", {"url": url, "allowed_updates": ["message"]})


def delete_webhook() -> dict:
    return _api("deleteWebhook")


def get_me() -> dict:
    return _api("getMe")


def set_commands() -> dict:
    """Register the bot command menu in Telegram."""
    commands = [
        {"command": "start", "description": "🔗 Vincular tu cuenta de Cadrex"},
        {"command": "help", "description": "❓ Ver lista de comandos disponibles"},
        {"command": "tareas", "description": "📋 Ver tus tareas pendientes"},
        {"command": "agregar", "description": "➕ Crear tarea por lenguaje natural"},
        {"command": "done", "description": "✅ Marcar tarea como completada"},
        {"command": "stats", "description": "📊 Estadísticas del dashboard"},
    ]
    return _api("setMyCommands", {"commands": commands})


# ── User resolution ──────────────────────────────────────────

def get_user_by_chat(chat_id: int) -> dict | None:
    rows = query(
        "SELECT u.* FROM kadrix_users u WHERE u.telegram_chat_id = %s AND u.active = 1",
        (chat_id,),
    )
    return rows[0] if rows else None


def link_chat_to_user(chat_id: int, username: str) -> dict | None:
    username = username.strip().lower().lstrip("@")
    rows = query(
        "SELECT id FROM kadrix_users WHERE username = %s AND active = 1",
        (username,),
    )
    if not rows:
        return None
    user_id = rows[0]["id"]
    execute(
        "UPDATE kadrix_users SET telegram_chat_id = %s WHERE id = %s",
        (chat_id, user_id),
    )
    execute(
        "INSERT INTO kadrix_telegram_sessions (user_id, chat_id) VALUES (%s, %s) "
        "ON DUPLICATE KEY UPDATE active=1",
        (user_id, chat_id),
    )
    return rows[0]


# ── Command handlers ─────────────────────────────────────────

_COMMANDS_HELP = """
🤖 *Bri — Comandos disponibles*

/start — Vincular tu cuenta de Telegram
/help — Mostrar este mensaje
/tareas — Ver tus tareas pendientes
/agregar <texto> — Crear tarea por lenguaje natural
/done <id> — Marcar tarea como completada
/stats — Ver estadísticas del dashboard

También puedes escribirme libremente para consultar datos de producción.
"""


def handle_update(update: dict) -> None:
    message = update.get("message", {})
    chat = message.get("chat", {})
    chat_id = chat.get("id")
    text = (message.get("text") or "").strip()
    if not chat_id or not text:
        return

    # Resolve user
    user = get_user_by_chat(chat_id)

    # --- /start ---
    if text.lower() == "/start":
        if user:
            send_message(chat_id, f"👋 Hola *{user['name']}*. Tu cuenta ya está vinculada. Escribe /help para ver comandos.")
            return
        send_message(
            chat_id,
            "👋 ¡Hola! Soy *Bri*, el asistente de Cadrex.\n\n"
            "Para vincular tu cuenta, escribe tu *username* de la app (ej: adriana).",
        )
        return

    # --- Linking flow (no command, no user) ---
    if not user and not text.startswith("/"):
        linked = link_chat_to_user(chat_id, text)
        if linked:
            send_message(chat_id, f"✅ Cuenta vinculada: *{linked.get('name', text)}*. Escribe /help para comenzar.")
        else:
            send_message(chat_id, f"❌ No encontré el usuario '*{text}*'. Verifica tu username e intenta de nuevo.")
        return

    if not user:
        send_message(chat_id, "⚠️ Escribe /start para vincular tu cuenta primero.")
        return

    # --- /help ---
    if text.lower() == "/help":
        send_message(chat_id, _COMMANDS_HELP)
        return

    # --- /tareas ---
    if text.lower() == "/tareas":
        tasks = query(
            """
            SELECT t.id, t.title, t.priority, t.due_date, c.name AS column_name
            FROM kadrix_tasks t
            JOIN kadrix_columns c ON t.column_id = c.id
            WHERE t.assigned_to = %s AND c.name != 'Done'
            ORDER BY t.priority DESC, t.due_date ASC
            LIMIT 10
            """,
            (user["id"],),
        )
        if not tasks:
            send_message(chat_id, "📭 No tienes tareas pendientes. ¡Buen trabajo!")
            return
        lines = [f"*Tus tareas pendientes:*\n"]
        for t in tasks:
            due = f" (vence {t['due_date']})" if t["due_date"] else ""
            lines.append(f"• #{t['id']} — *{t['title']}* [{t['priority']}]{due}")
        send_message(chat_id, "\n".join(lines))
        return

    # --- /done <id> ---
    if text.lower().startswith("/done"):
        parts = text.split(None, 1)
        if len(parts) < 2:
            send_message(chat_id, "Uso: `/done <id_tarea>`")
            return
        try:
            task_id = int(parts[1].strip())
        except ValueError:
            send_message(chat_id, "❌ ID de tarea inválido.")
            return
        done_col = query(
            "SELECT id FROM kadrix_columns WHERE board_id = (SELECT board_id FROM kadrix_tasks WHERE id = %s) AND name = 'Done' LIMIT 1",
            (task_id,),
        )
        if not done_col:
            send_message(chat_id, "❌ No se encontró la columna 'Done'.")
            return
        execute(
            "UPDATE kadrix_tasks SET column_id = %s WHERE id = %s AND assigned_to = %s",
            (done_col[0]["id"], task_id, user["id"]),
        )
        send_message(chat_id, f"✅ Tarea #{task_id} movida a *Done*.")
        return

    # --- /stats ---
    if text.lower() == "/stats":
        total = query("SELECT COUNT(*) AS n FROM kadrix_tasks WHERE assigned_to = %s", (user["id"],))
        pending = query(
            "SELECT COUNT(*) AS n FROM kadrix_tasks t JOIN kadrix_columns c ON t.column_id = c.id "
            "WHERE t.assigned_to = %s AND c.name != 'Done'",
            (user["id"],),
        )
        overdue = query(
            "SELECT COUNT(*) AS n FROM kadrix_tasks t JOIN kadrix_columns c ON t.column_id = c.id "
            "WHERE t.assigned_to = %s AND c.name != 'Done' AND t.due_date < CURDATE()",
            (user["id"],),
        )
        msg = (
            f"📊 *Tus estadísticas:*\n"
            f"• Total asignadas: {total[0]['n']}\n"
            f"• Pendientes: {pending[0]['n']}\n"
            f"• Vencidas: {overdue[0]['n']}"
        )
        send_message(chat_id, msg)
        return

    # --- /agregar <texto> ---
    if text.lower().startswith("/agregar"):
        parts = text.split(None, 1)
        if len(parts) < 2:
            send_message(chat_id, "Uso: `/agregar Crea tarea para revisar estación 4 mañana`")
            return
        # Defer to nl_tasks
        from kadrix.nl_tasks import create_task_from_text
        result = create_task_from_text(parts[1], user)
        send_message(chat_id, result["message"])
        return

    # --- Free text chat (Bri AI) ---
    from app import _get_user_chat_history, _append_chat_turn, _build_chat_context
    user_key = f"telegram:{user['username']}"
    history = _get_user_chat_history(user_key)
    messages = [{"role": "system", "content": _build_chat_context(user["username"], mode="production")}]
    for turn in history[-10:]:
        role = turn.get("role", "")
        content = str(turn.get("content", ""))
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": text})

    import os as _os
    api_key = _os.getenv("OPENROUTER_API_KEY", "")
    model = _os.getenv("OPENROUTER_MODEL", "anthropic/claude-3-haiku")
    if not api_key:
        send_message(chat_id, "⚠️ OpenRouter no está configurado.")
        return

    try:
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "HTTP-Referer": "https://soul23.mx",
                "X-Title": "Cadrex Bri Assistant Telegram",
            },
            json={
                "model": model,
                "messages": messages,
                "max_tokens": 700,
                "temperature": 0.65,
            },
            timeout=28,
        )
        resp.raise_for_status()
        reply = resp.json()["choices"][0]["message"]["content"]
        _append_chat_turn(user_key, "user", text)
        _append_chat_turn(user_key, "assistant", reply)
        send_message(chat_id, reply)
    except Exception as exc:
        logger.warning("Telegram chat error: %s", exc)
        send_message(chat_id, "⚠️ No pude procesar tu mensaje. Intenta de nuevo.")
