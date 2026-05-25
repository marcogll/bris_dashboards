CREATE TABLE IF NOT EXISTS actas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_name TEXT NOT NULL,
    employee_id TEXT DEFAULT '',
    acta_type TEXT NOT NULL,
    description TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pendiente',
    created_by TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS acta_types (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT NOT NULL UNIQUE,
    label TEXT NOT NULL
);

INSERT OR IGNORE INTO acta_types (key, label) VALUES ('falta', 'Falta');
INSERT OR IGNORE INTO acta_types (key, label) VALUES ('retardo', 'Retardo');
INSERT OR IGNORE INTO acta_types (key, label) VALUES ('sancion', 'Sanción');
INSERT OR IGNORE INTO acta_types (key, label) VALUES ('verbal', 'Amonestación Verbal');
INSERT OR IGNORE INTO acta_types (key, label) VALUES ('escrita', 'Amonestación Escrita');