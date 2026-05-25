"""Cadrex — MySQL connection helper (MODO OFFLINE - sin MySQL)."""
import logging
from typing import Any

logger = logging.getLogger("kadrix")

# MODO OFFLINE: no se conecta a MySQL. Retorna siempre vacío.
def query(sql: str, params: tuple | None = None) -> list[dict[str, Any]]:
    """Offline mode — returns empty list."""
    return []


def execute(sql: str, params: tuple | None = None) -> int:
    """Offline mode — returns 0."""
    return 0
