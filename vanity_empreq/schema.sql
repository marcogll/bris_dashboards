CREATE TABLE IF NOT EXISTS solicitudes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_name TEXT NOT NULL,
    employee_id TEXT DEFAULT '',
    request_type TEXT NOT NULL,
    description TEXT DEFAULT '',
    start_date TEXT DEFAULT '',
    end_date TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pendiente',
    created_by TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS request_types (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT NOT NULL UNIQUE,
    label TEXT NOT NULL
);

INSERT OR IGNORE INTO request_types (key, label) VALUES ('vacaciones', 'Vacaciones');
INSERT OR IGNORE INTO request_types (key, label) VALUES ('permiso', 'Permiso');
INSERT OR IGNORE INTO request_types (key, label) VALUES ('incapacidad', 'Incapacidad');