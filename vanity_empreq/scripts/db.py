import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB = BASE_DIR / "instance" / "vanity_empreq.db"
SCHEMA = BASE_DIR / "schema.sql"


def connect(db_path=None):
    if db_path is None:
        db_path = DEFAULT_DB
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn):
    conn.executescript(SCHEMA.read_text())
    conn.commit()