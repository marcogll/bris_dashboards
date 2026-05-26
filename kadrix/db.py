"""Cadrex — MySQL connection helper."""
import logging
import os
import re
import time
from typing import Any

from flask import g, has_request_context

try:
    import mysql.connector
    from mysql.connector import Error
    _MYSQL_AVAILABLE = True
except ModuleNotFoundError:
    _MYSQL_AVAILABLE = False
    mysql = None  # type: ignore

logger = logging.getLogger("kadrix")
SLOW_QUERY_MS = float(os.getenv("CADREX_DB_SLOW_MS", "250"))

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


def _request_id() -> str:
    if has_request_context():
        return getattr(g, "request_id", "-")
    return "-"


def _sql_summary(sql: str) -> str:
    compact = " ".join(sql.split())
    match = re.search(r"\b(FROM|INTO|UPDATE|JOIN)\s+`?([a-zA-Z0-9_]+)`?", compact, re.IGNORECASE)
    table = match.group(2) if match else "-"
    verb = compact.split(" ", 1)[0].upper() if compact else "SQL"
    return f"{verb} table={table}"


def get_conn():
    _check()
    try:
        started = time.perf_counter()
        conn = mysql.connector.connect(**MYSQL_CONFIG)  # type: ignore
        elapsed_ms = (time.perf_counter() - started) * 1000
        if elapsed_ms >= SLOW_QUERY_MS:
            logger.warning(
                "db_connect_slow duration_ms=%.1f host=%s database=%s",
                elapsed_ms,
                MYSQL_CONFIG["host"],
                MYSQL_CONFIG["database"],
                extra={"request_id": _request_id()},
            )
        return conn
    except Exception as exc:
        raise RuntimeError(f"Cadrex DB error: {exc}") from exc


def query(sql: str, params: tuple | None = None) -> list[dict[str, Any]]:
    started = time.perf_counter()
    summary = _sql_summary(sql)
    try:
        conn = get_conn()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(sql, params or ())
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        elapsed_ms = (time.perf_counter() - started) * 1000
        if elapsed_ms >= SLOW_QUERY_MS:
            logger.warning(
                "db_query_slow %s rows=%s duration_ms=%.1f",
                summary,
                len(rows),
                elapsed_ms,
                extra={"request_id": _request_id()},
            )
        return rows
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - started) * 1000
        logger.warning(
            "db_query_failed %s duration_ms=%.1f error=%s",
            summary,
            elapsed_ms,
            exc,
            extra={"request_id": _request_id()},
        )
        return []


def execute(sql: str, params: tuple | None = None) -> int:
    started = time.perf_counter()
    summary = _sql_summary(sql)
    try:
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute(sql, params or ())
        last_id = cursor.lastrowid
        conn.commit()
        cursor.close()
        conn.close()
        elapsed_ms = (time.perf_counter() - started) * 1000
        if elapsed_ms >= SLOW_QUERY_MS:
            logger.warning(
                "db_execute_slow %s last_id=%s duration_ms=%.1f",
                summary,
                last_id,
                elapsed_ms,
                extra={"request_id": _request_id()},
            )
        return last_id
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - started) * 1000
        logger.warning(
            "db_execute_failed %s duration_ms=%.1f error=%s",
            summary,
            elapsed_ms,
            exc,
            extra={"request_id": _request_id()},
        )
        return 0
