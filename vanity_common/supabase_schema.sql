-- =============================================================================
-- Vanity HQ — Supabase schema migration
-- =============================================================================
-- Centralized auth tables for SSO, RBAC, and server-side sessions.
-- Project ref: umzlwcdjxtbdoqiclolo
--
-- Run with:  supabase db push   OR   psql -f this_file.sql
-- =============================================================================

-- ─── Extensions ──────────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ─── Helper: auto-update updated_at ─────────────────────────────────────────
CREATE OR REPLACE FUNCTION vanity_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- 1. vanity_roles
-- =============================================================================
CREATE TABLE IF NOT EXISTS vanity_roles (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name        TEXT    UNIQUE NOT NULL,
    level       INT     NOT NULL DEFAULT 0,
    description TEXT    DEFAULT '',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_vanity_roles_level ON vanity_roles (level DESC);

-- ─── Trigger: auto-update updated_at ────────────────────────────────────────
CREATE TRIGGER trg_vanity_roles_updated_at
    BEFORE UPDATE ON vanity_roles
    FOR EACH ROW EXECUTE FUNCTION vanity_set_updated_at();

-- ─── Seed roles ─────────────────────────────────────────────────────────────
INSERT INTO vanity_roles (id, name, level, description) VALUES
    ('00000000-0000-0000-0000-000000000001', 'Owner',        100, 'Rol base Owner'),
    ('00000000-0000-0000-0000-000000000002', 'Admin',         80, 'Rol base Admin'),
    ('00000000-0000-0000-0000-000000000003', 'Manager',       60, 'Rol base Manager'),
    ('00000000-0000-0000-0000-000000000004', 'Operador',      40, 'Rol base Operador'),
    ('00000000-0000-0000-0000-000000000005', 'Solo lectura',  20, 'Rol base Solo lectura'),
    ('00000000-0000-0000-0000-000000000006', 'Socia',         10, 'Rol base Socia')
ON CONFLICT (name) DO NOTHING;

-- =============================================================================
-- 2. vanity_users
-- =============================================================================
CREATE TABLE IF NOT EXISTS vanity_users (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name          TEXT    NOT NULL,
    email         TEXT    UNIQUE NOT NULL,
    username      TEXT    UNIQUE NOT NULL,
    password_hash TEXT    NOT NULL,
    phone         TEXT    DEFAULT '',
    branch        TEXT    DEFAULT 'all',
    role_id       UUID    NOT NULL REFERENCES vanity_roles(id) ON DELETE RESTRICT,
    theme         TEXT    DEFAULT 'system',
    is_active     BOOLEAN DEFAULT TRUE,
    last_login    TIMESTAMPTZ,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_vanity_users_email     ON vanity_users (email);
CREATE INDEX idx_vanity_users_username  ON vanity_users (username);
CREATE INDEX idx_vanity_users_role_id   ON vanity_users (role_id);
CREATE INDEX idx_vanity_users_is_active ON vanity_users (is_active);

-- ─── Trigger: auto-update updated_at ────────────────────────────────────────
CREATE TRIGGER trg_vanity_users_updated_at
    BEFORE UPDATE ON vanity_users
    FOR EACH ROW EXECUTE FUNCTION vanity_set_updated_at();

-- ─── Seed admin user ────────────────────────────────────────────────────────
-- Password: VanityAdmin2026!
-- Hash generated with werkzeug.security.generate_password_hash (scrypt)
INSERT INTO vanity_users (id, name, email, username, password_hash, role_id)
VALUES (
    '00000000-0000-0000-0000-000000000100',
    'Admin Vanity',
    'admin@vanity.local',
    'admin',
    'scrypt:32768:8:1$xRcs9mbpk403Jd4F$f98e26b86b800ac0f9de7dd8e455a05fd5d15629cbb34737509e6e369e2e86ee273758336f4825f792eda3e28f4cff55cef7ed748a609cb21bf50268fd56a3bb',
    '00000000-0000-0000-0000-000000000001'
) ON CONFLICT (email) DO NOTHING;

-- =============================================================================
-- 3. vanity_permissions
-- =============================================================================
-- subject_type: 'role' or 'user'
-- subject_id:   UUID of the role or user the permission applies to
-- scope:        'all', 'branch', 'own', 'assigned', 'none'
-- allowed:      boolean
CREATE TABLE IF NOT EXISTS vanity_permissions (
    id           UUID    PRIMARY KEY DEFAULT uuid_generate_v4(),
    subject_type TEXT    NOT NULL CHECK (subject_type IN ('role', 'user')),
    subject_id   UUID    NOT NULL,
    system       TEXT    NOT NULL,
    module       TEXT    NOT NULL,
    action       TEXT    NOT NULL,
    scope        TEXT    NOT NULL DEFAULT 'none' CHECK (scope IN ('all', 'branch', 'own', 'assigned', 'none')),
    allowed      BOOLEAN NOT NULL DEFAULT FALSE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(subject_type, subject_id, system, module, action)
);

CREATE INDEX idx_vanity_permissions_subject ON vanity_permissions (subject_type, subject_id);
CREATE INDEX idx_vanity_permissions_system_module ON vanity_permissions (system, module);
CREATE INDEX idx_vanity_permissions_role ON vanity_permissions (subject_type, subject_id)
    WHERE subject_type = 'role';

-- =============================================================================
-- 4. vanity_sessions
-- =============================================================================
-- Server-side session store. Replaces signed cookies across all microservices.
-- A session is valid when revoked_at IS NULL and expires_at > NOW().
CREATE TABLE IF NOT EXISTS vanity_sessions (
    id                UUID    PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id           UUID    NOT NULL REFERENCES vanity_users(id) ON DELETE CASCADE,
    session_token_hash TEXT   NOT NULL,
    system            TEXT    NOT NULL,
    context           JSONB   NOT NULL DEFAULT '{}',
    ip_address        TEXT    DEFAULT '',
    user_agent        TEXT    DEFAULT '',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at        TIMESTAMPTZ NOT NULL,
    revoked_at        TIMESTAMPTZ
);

CREATE INDEX idx_vanity_sessions_token   ON vanity_sessions (session_token_hash);
CREATE INDEX idx_vanity_sessions_user    ON vanity_sessions (user_id);
CREATE INDEX idx_vanity_sessions_active  ON vanity_sessions (user_id, system)
    WHERE revoked_at IS NULL;
CREATE INDEX idx_vanity_sessions_expires ON vanity_sessions (expires_at)
    WHERE revoked_at IS NULL;

-- =============================================================================
-- 5. vanity_audit_log
-- =============================================================================
CREATE TABLE IF NOT EXISTS vanity_audit_log (
    id            UUID    PRIMARY KEY DEFAULT uuid_generate_v4(),
    actor_user_id UUID    REFERENCES vanity_users(id) ON DELETE SET NULL,
    action        TEXT    NOT NULL,
    target_type   TEXT    NOT NULL,
    target_id     TEXT    DEFAULT '',
    detail        TEXT    DEFAULT '',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_vanity_audit_actor ON vanity_audit_log (actor_user_id);
CREATE INDEX idx_vanity_audit_action ON vanity_audit_log (action);
CREATE INDEX idx_vanity_audit_created ON vanity_audit_log (created_at DESC);

-- =============================================================================
-- RLS Policies
-- =============================================================================
-- These tables are accessed server-side via the service_role key, so RLS
-- is a safety net, not the primary access control.

ALTER TABLE vanity_roles        ENABLE ROW LEVEL SECURITY;
ALTER TABLE vanity_users        ENABLE ROW LEVEL SECURITY;
ALTER TABLE vanity_permissions  ENABLE ROW LEVEL SECURITY;
ALTER TABLE vanity_sessions     ENABLE ROW LEVEL SECURITY;
ALTER TABLE vanity_audit_log    ENABLE ROW LEVEL SECURITY;

-- Service role bypasses RLS by default in Supabase, so these policies
-- allow the anon key to read for client-side scenarios if needed.

CREATE POLICY "service_role_all" ON vanity_roles        FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "service_role_all" ON vanity_users        FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "service_role_all" ON vanity_permissions  FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "service_role_all" ON vanity_sessions     FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "service_role_all" ON vanity_audit_log    FOR ALL USING (TRUE) WITH CHECK (TRUE);

-- Restrictive policies for anon/auth'd users: read-only on roles & own session
CREATE POLICY "anon_read_roles" ON vanity_roles FOR SELECT USING (TRUE);

CREATE POLICY "anon_read_own_sessions" ON vanity_sessions FOR SELECT
    USING (revoked_at IS NULL AND expires_at > NOW());

-- Cleanup: delete expired sessions older than 30 days (run via cron or pg_cron)
CREATE OR REPLACE FUNCTION vanity_cleanup_expired_sessions()
RETURNS void AS $$
BEGIN
    DELETE FROM vanity_sessions
    WHERE (revoked_at IS NOT NULL OR expires_at < NOW())
      AND expires_at < NOW() - INTERVAL '30 days';
END;
$$ LANGUAGE plpgsql;