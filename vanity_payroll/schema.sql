-- Vanity Payroll - Database Schema
-- SQLite schema for the payroll management system.

CREATE TABLE IF NOT EXISTS people (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL,
    normalized_name TEXT NOT NULL DEFAULT '',
    email TEXT DEFAULT '',
    phone TEXT DEFAULT '',
    branch_name TEXT DEFAULT '',
    employee_number TEXT DEFAULT '',
    relationship_type TEXT DEFAULT 'mercantil',
    contract_type TEXT DEFAULT 'mercantil',
    start_date TEXT DEFAULT '',
    end_date TEXT DEFAULT '',
    payment_day TEXT DEFAULT '',
    tax_id TEXT DEFAULT '',
    curp TEXT DEFAULT '',
    bank_name TEXT DEFAULT '',
    bank_account TEXT DEFAULT '',
    clabe TEXT DEFAULT '',
    status TEXT DEFAULT 'active',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS payroll_concepts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    concept_type TEXT NOT NULL CHECK (concept_type IN ('earning', 'deduction')),
    taxable INTEGER DEFAULT 1,
    active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS payroll_periods (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    frequency TEXT DEFAULT 'weekly',
    starts_on TEXT NOT NULL,
    ends_on TEXT NOT NULL,
    status TEXT DEFAULT 'draft',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS payroll_payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    period_id INTEGER NOT NULL,
    person_id INTEGER NOT NULL,
    person_snapshot TEXT DEFAULT '',
    relationship_type TEXT DEFAULT '',
    gross_amount REAL DEFAULT 0,
    deductions_amount REAL DEFAULT 0,
    net_amount REAL DEFAULT 0,
    bono_punt_eligible INTEGER DEFAULT 1,
    bono_ext_eligible INTEGER DEFAULT 1,
    status TEXT DEFAULT 'draft',
    approved_by TEXT DEFAULT '',
    approved_at TEXT DEFAULT '',
    paid_at TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (period_id) REFERENCES payroll_periods(id),
    FOREIGN KEY (person_id) REFERENCES people(id)
);

CREATE TABLE IF NOT EXISTS payment_lines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    payment_id INTEGER NOT NULL,
    concept_code TEXT NOT NULL,
    description TEXT DEFAULT '',
    amount REAL DEFAULT 0,
    source_type TEXT DEFAULT 'calculation',
    source_id TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    FOREIGN KEY (payment_id) REFERENCES payroll_payments(id)
);

CREATE TABLE IF NOT EXISTS payment_receipts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    payment_id INTEGER NOT NULL,
    folio TEXT NOT NULL,
    receipt_type TEXT DEFAULT 'internal',
    status TEXT DEFAULT 'draft',
    file_path TEXT DEFAULT '',
    signed_at TEXT DEFAULT '',
    validated_at TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    FOREIGN KEY (payment_id) REFERENCES payroll_payments(id)
);

CREATE TABLE IF NOT EXISTS payment_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    payment_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    actor TEXT DEFAULT '',
    detail TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    FOREIGN KEY (payment_id) REFERENCES payroll_payments(id)
);

CREATE TABLE IF NOT EXISTS contracts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id INTEGER NOT NULL,
    contract_type TEXT DEFAULT 'mercantil',
    base_salary REAL DEFAULT 0,
    commission_rate REAL DEFAULT 0,
    rules_json TEXT DEFAULT '{}',
    status TEXT DEFAULT 'active',
    effective_from TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (person_id) REFERENCES people(id)
);

CREATE TABLE IF NOT EXISTS sales_appointments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ref_cita TEXT UNIQUE,
    client_name TEXT DEFAULT '',
    staff_name TEXT DEFAULT '',
    staff_normalized_name TEXT DEFAULT '',
    resource TEXT DEFAULT '',
    status TEXT DEFAULT '',
    created_at_source TEXT DEFAULT '',
    scheduled_at TEXT DEFAULT '',
    cancelled_at TEXT DEFAULT '',
    category TEXT DEFAULT '',
    service TEXT DEFAULT '',
    duration_original TEXT DEFAULT '',
    duration_minutes INTEGER DEFAULT 0,
    time_slot TEXT DEFAULT '',
    created_by TEXT DEFAULT '',
    cancelled_by TEXT DEFAULT '',
    center_name TEXT DEFAULT '',
    branch_code TEXT DEFAULT '',
    net_sales REAL DEFAULT 0,
    cancellation_reason TEXT DEFAULT '',
    surcharges REAL DEFAULT 0,
    prepayments REAL DEFAULT 0,
    person_id INTEGER,
    source_file TEXT DEFAULT '',
    raw_payload TEXT DEFAULT '',
    imported_at TEXT DEFAULT '',
    FOREIGN KEY (person_id) REFERENCES people(id)
);

CREATE TABLE IF NOT EXISTS import_batches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT DEFAULT '',
    file_name TEXT DEFAULT '',
    rows_total INTEGER DEFAULT 0,
    rows_inserted INTEGER DEFAULT 0,
    rows_updated INTEGER DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS payroll_run_imports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    import_batch_id INTEGER,
    matched_person_id INTEGER,
    source_scheme TEXT DEFAULT '',
    row_number INTEGER DEFAULT 0,
    created_at TEXT DEFAULT '',
    FOREIGN KEY (import_batch_id) REFERENCES import_batches(id),
    FOREIGN KEY (matched_person_id) REFERENCES people(id)
);

CREATE TABLE IF NOT EXISTS contract_roster_imports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    import_batch_id INTEGER,
    matched_person_id INTEGER,
    row_number INTEGER DEFAULT 0,
    status TEXT DEFAULT '',
    end_date TEXT DEFAULT '',
    baja_reason TEXT DEFAULT '',
    created_at TEXT DEFAULT '',
    FOREIGN KEY (import_batch_id) REFERENCES import_batches(id),
    FOREIGN KEY (matched_person_id) REFERENCES people(id)
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_people_status ON people(status);
CREATE INDEX IF NOT EXISTS idx_people_normalized_name ON people(normalized_name);
CREATE INDEX IF NOT EXISTS idx_people_employee_number ON people(employee_number);
CREATE INDEX IF NOT EXISTS idx_people_email ON people(email);
CREATE INDEX IF NOT EXISTS idx_people_contract_type ON people(contract_type);
CREATE INDEX IF NOT EXISTS idx_payroll_payments_person_id ON payroll_payments(person_id);
CREATE INDEX IF NOT EXISTS idx_payroll_payments_period_id ON payroll_payments(period_id);
CREATE INDEX IF NOT EXISTS idx_payroll_payments_status ON payroll_payments(status);
CREATE INDEX IF NOT EXISTS idx_payment_lines_payment_id ON payment_lines(payment_id);
CREATE INDEX IF NOT EXISTS idx_payment_receipts_payment_id ON payment_receipts(payment_id);
CREATE INDEX IF NOT EXISTS idx_payment_history_payment_id ON payment_history(payment_id);
CREATE INDEX IF NOT EXISTS idx_contracts_person_id ON contracts(person_id);
CREATE INDEX IF NOT EXISTS idx_sales_appointments_person_id ON sales_appointments(person_id);
CREATE INDEX IF NOT EXISTS idx_sales_appointments_scheduled_at ON sales_appointments(scheduled_at);
CREATE INDEX IF NOT EXISTS idx_sales_appointments_staff_normalized_name ON sales_appointments(staff_normalized_name);
CREATE INDEX IF NOT EXISTS idx_payroll_periods_status ON payroll_periods(status);
CREATE INDEX IF NOT EXISTS idx_payroll_run_imports_batch_id ON payroll_run_imports(import_batch_id);
CREATE INDEX IF NOT EXISTS idx_contract_roster_imports_batch_id ON contract_roster_imports(import_batch_id);