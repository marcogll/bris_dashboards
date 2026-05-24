"""Cadrex — MySQL connection helper."""
import logging
import os
from typing import Any

try:
    import mysql.connector
    from mysql.connector import Error
    _MYSQL_AVAILABLE = True
except ModuleNotFoundError:
    _MYSQL_AVAILABLE = False
    mysql = None  # type: ignore

logger = logging.getLogger("kadrix")

MYSQL_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "127.0.0.1"),
    "port": int(os.getenv("MYSQL_PORT", "3306")),
    "user": os.getenv("MYSQL_USER", "bris_user"),
    "password": os.getenv("MYSQL_PASSWORD", "bris_password"),
    "database": os.getenv("MYSQL_DATABASE", "bris_adriana"),
    "autocommit": True,
}


def _check():
    if not _MYSQL_AVAILABLE:
        raise RuntimeError("mysql-connector-python no está instalado. Ejecuta: pip install mysql-connector-python")


def get_conn():
    _check()
    try:
        return mysql.connector.connect(**MYSQL_CONFIG)  # type: ignore
    except Exception as exc:
        raise RuntimeError(f"Cadrex DB error: {exc}") from exc


def query(sql: str, params: tuple | None = None) -> list[dict[str, Any]]:
    try:
        conn = get_conn()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(sql, params or ())
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return rows
    except RuntimeError as exc:
        logger.warning("Cadrex query skipped (DB unavailable): %s", exc)
        return []


def execute(sql: str, params: tuple | None = None) -> int:
    try:
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute(sql, params or ())
        last_id = cursor.lastrowid
        conn.commit()
        cursor.close()
        conn.close()
        return last_id
    except RuntimeError as exc:
        logger.warning("Cadrex execute skipped (DB unavailable): %s", exc)
        return 0
