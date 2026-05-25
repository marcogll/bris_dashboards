"""Cadrix — Fizzy (Basecamp) API Client.
Fizzy is a 37signals kanban tool. This is a thin HTTP client.
Docs: https://github.com/basecamp/fizzy
"""
import logging
import os
from typing import Any

import requests

logger = logging.getLogger("bris_dashboard.fizzy")

FIZZY_API_KEY = os.getenv("FIZZY_API_KEY", "")
FIZZY_BASE_URL = os.getenv("FIZZY_BASE_URL", "https://fizzy-br.soul23.cloud").rstrip("/")


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {FIZZY_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _request(method: str, path: str, json_data: dict | None = None) -> dict:
    if not FIZZY_API_KEY:
        return {"error": "FIZZY_API_KEY not configured"}
    url = f"{FIZZY_BASE_URL}{path}"
    try:
        resp = requests.request(method, url, headers=_headers(), json=json_data, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except requests.HTTPError as exc:
        try:
            body = exc.response.json()
        except Exception:
            body = {"message": exc.response.text}
        logger.warning("Fizzy HTTP %s: %s", exc.response.status_code, body)
        return {"error": body}
    except Exception as exc:
        logger.warning("Fizzy request error: %s", exc)
        return {"error": str(exc)}


# ── Boards (projects in Fizzy) ───────────────────────────────

def list_boards() -> list[dict]:
    data = _request("GET", "/api/v1/boards")
    return data if isinstance(data, list) else []


def get_board(board_id: str) -> dict:
    return _request("GET", f"/api/v1/boards/{board_id}")


# ── Cards (todos in Fizzy) ───────────────────────────────────

def list_cards(board_id: str) -> list[dict]:
    data = _request("GET", f"/api/v1/boards/{board_id}/cards")
    return data if isinstance(data, list) else []


def create_card(board_id: str, title: str, description: str = "", status: str = "open") -> dict:
    return _request("POST", f"/api/v1/boards/{board_id}/cards", {
        "title": title,
        "description": description,
        "status": status,
    })


def update_card(card_id: str, fields: dict) -> dict:
    return _request("PATCH", f"/api/v1/cards/{card_id}", fields)


def complete_card(card_id: str) -> dict:
    return update_card(card_id, {"status": "completed"})


# ── Sync helpers ─────────────────────────────────────────────

def sync_task_to_fizzy(kadrix_task: dict, fizzy_board_id: str | None = None) -> dict:
    """Create or update a Fizzy card from a Kadrix task."""
    board_id = fizzy_board_id or os.getenv("FIZZY_DEFAULT_BOARD_ID", "")
    if not board_id:
        return {"error": "No Fizzy board_id configured"}

    title = kadrix_task.get("title", "Sin título")
    desc = kadrix_task.get("description", "")
    status = "completed" if kadrix_task.get("column_name") == "Done" else "open"

    # Check if already synced
    from kadrix.db import query
    sync_row = query(
        "SELECT basecamp_todo_id FROM kadrix_basecamp_sync WHERE kadrix_task_id = %s",
        (kadrix_task["id"],),
    )
    if sync_row:
        todo_id = sync_row[0]["basecamp_todo_id"]
        result = update_card(todo_id, {
            "title": title,
            "description": desc,
            "status": status,
        })
        return result

    result = create_card(board_id, title, desc, status)
    if "error" not in result and "id" in result:
        from kadrix.db import execute
        execute(
            "INSERT INTO kadrix_basecamp_sync (kadrix_task_id, basecamp_todo_id, basecamp_project_id) VALUES (%s, %s, %s)",
            (kadrix_task["id"], str(result["id"]), board_id),
        )
    return result


def import_from_fizzy(board_id: str | None = None) -> dict:
    """Pull cards from Fizzy and create Kadrix tasks."""
    board_id = board_id or os.getenv("FIZZY_DEFAULT_BOARD_ID", "")
    if not board_id:
        return {"error": "No Fizzy board_id configured"}

    cards = list_cards(board_id)
    created = 0
    skipped = 0

    from kadrix.db import execute, query

    for card in cards:
        card_id = str(card.get("id", ""))
        if not card_id:
            continue
        existing = query(
            "SELECT id FROM kadrix_basecamp_sync WHERE basecamp_todo_id = %s",
            (card_id,),
        )
        if existing:
            skipped += 1
            continue

        title = card.get("title", "Sin título")
        desc = card.get("description", "")
        status = card.get("status", "open")
        col_name = "Done" if status == "completed" else "Backlog"
        col = query(
            "SELECT id FROM kadrix_columns WHERE board_id = 1 AND name = %s LIMIT 1",
            (col_name,),
        )
        col_id = col[0]["id"] if col else None
        if not col_id:
            continue

        tid = execute(
            "INSERT INTO kadrix_tasks (board_id, column_id, title, description, priority, created_by) VALUES (%s, %s, %s, %s, %s, %s)",
            (1, col_id, title, desc, "medium", None),
        )
        if tid:
            execute(
                "INSERT INTO kadrix_basecamp_sync (kadrix_task_id, basecamp_todo_id, basecamp_project_id) VALUES (%s, %s, %s)",
                (tid, card_id, board_id),
            )
            created += 1

    return {"created": created, "skipped": skipped, "total": len(cards)}
