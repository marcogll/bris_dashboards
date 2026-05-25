import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "instance" / "vanity_payroll.db"


def connect(db_path=None):
    path = Path(db_path) if db_path else DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn):
    conn.executescript((BASE_DIR / "schema.sql").read_text())
    seed_concepts(conn)
    conn.commit()


def seed_concepts(conn):
    concepts = [
        ("HOURLY_PAY", "Pago base por horas", "earning", 1),
        ("SALES_COMMISSION", "Comision por ventas", "earning", 1),
        ("PUNCTUALITY_BONUS", "Bono puntualidad", "earning", 1),
        ("EXTRA_BONUS", "Bono extra", "earning", 1),
        ("ADJUSTMENT", "Ajuste redondeo", "earning", 0),
        ("ADVANCE", "Anticipo", "deduction", 0),
        ("MANUAL_DEDUCTION", "Deduccion manual", "deduction", 0),
        ("IMSS", "Retencion IMSS", "deduction", 0),
        ("ISR", "ISR", "deduction", 0),
    ]
    conn.executemany(
        """
        INSERT OR IGNORE INTO payroll_concepts (code, name, concept_type, taxable, active)
        VALUES (?, ?, ?, ?, 1)
        """,
        concepts,
    )


def scalar(query, params=(), db_path=None):
    with connect(db_path) as conn:
        row = conn.execute(query, params).fetchone()
        return row[0] if row else None