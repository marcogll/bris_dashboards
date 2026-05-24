# =============================================================================
# Vanity HQ Wrapper - Central Authentication & RBAC Service
# =============================================================================
# Proxy central de autenticacion SSO y control de permisos RBAC para todos
# los microservicios de Vanity HQ.
#
# Flujo SSO:
#   1. Usuario hace login en /login
#   2. Al lanzar un servicio (/launch/<system_key>), se emite un token
#      URLSafeTimedSerializer firmado con VANITY_HQ_SECRET_KEY
#   3. El servicio downstream valida en /auth/hq?token=...
#   4. Los servicios tambien pueden validar via POST /api/auth/validate-token
#
# Modelo de permisos:
#   Roles: Owner(100), Admin(80), Manager(60), Operador(40), Solo lectura(20), Socia(10)
#   Scopes: all, branch, own, assigned, none
#   Acciones: view, create, edit, delete, approve, reject, export, import, configure, archive, restore
#
# Env vars requeridas:
#   VANITY_HQ_SECRET_KEY - Clave de firma de tokens y sesiones
#   VANITY_HQ_TOKEN_MAX_AGE - Tiempo de vida del token en segundos (default: 43200 = 12h)
#   VANITY_*_PUBLIC_URL - URLs publicas de cada servicio downstream
#   PORT - Puerto de escucha (default: 5050)
#
# Base de datos: SQLite en instance/vanity_hq.db
# Tablas: roles, users, permissions, audit_log
# =============================================================================

import os
import sqlite3
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path

from flask import Flask, flash, g, jsonify, redirect, render_template, request, session, url_for
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash


BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"
DB_PATH = INSTANCE_DIR / "vanity_hq.db"
TOKEN_MAX_AGE = int(os.getenv("VANITY_HQ_TOKEN_MAX_AGE", "43200"))

# --- Registro de sistemas downstream ----------------------------------------
# Cada entrada define un microservicio accesible desde el launcher de HQ.
# "modules" define los modulos de permisos disponibles para ese sistema.
SYSTEMS = {
    "vanity_dashboard": {
        "name": "Dashboard",
        "description": "Ventas, citas, staff performance y rentabilidad.",
        "url": os.getenv("VANITY_DASHBOARD_PUBLIC_URL", os.getenv("VANITY_DASHBOARD_URL", "http://127.0.0.1:5001")),
        "modules": ["sales", "appointments", "staff_performance", "inventory", "reports", "settings"],
    },
    "vanity_hrmgr": {
        "name": "HR Manager",
        "description": "Socias, vacaciones, permisos, incidencias y documentos.",
        "url": os.getenv("VANITY_HRMGR_PUBLIC_URL", os.getenv("VANITY_HRMGR_URL", "http://127.0.0.1:8000")),
        "modules": ["employees", "branches", "requests", "absences", "holidays", "documents", "reports", "settings"],
    },
    "vanity_payroll": {
        "name": "Payroll",
        "description": "Nomina, pagos, recibos, aprobaciones e historial.",
        "url": os.getenv("VANITY_PAYROLL_PUBLIC_URL", os.getenv("VANITY_PAYROLL_URL", "http://127.0.0.1:5051")),
        "modules": ["people", "sales", "periods", "payments", "receipts", "concepts", "approvals", "history", "reports", "settings"],
    },
    "vanity_empreq": {
        "name": "EmpReq",
        "description": "Solicitudes de vacaciones, permisos e incapacidades.",
        "url": os.getenv("VANITY_EMPREQ_PUBLIC_URL", os.getenv("VANITY_EMPREQ_URL", "http://127.0.0.1:5053")),
        "modules": ["requests", "settings"],
    },
    "vanity_actas": {
        "name": "Actas Administrativas",
        "description": "Registro de actas, faltas, retardos y sanciones.",
        "url": os.getenv("VANITY_ACTAS_PUBLIC_URL", os.getenv("VANITY_ACTAS_URL", "http://127.0.0.1:5052")),
        "modules": ["actas", "settings"],
    },
    "vanity_hq": {
        "name": "HQ Admin",
        "description": "Usuarios, roles, permisos, sistemas y auditoria global.",
        "url": "/hq",
        "modules": ["users", "roles", "permissions", "audit", "settings", "systems"],
    },
}

# --- Acciones, scopes y niveles de rol --------------------------------------
ACTIONS = ["view", "create", "edit", "delete", "approve", "reject", "export", "import", "configure", "archive", "restore"]
SCOPES = ["all", "branch", "own", "assigned", "none"]
ROLE_LEVELS = {
    "Owner": 100,
    "Admin": 80,
    "Manager": 60,
    "Operador": 40,
    "Solo lectura": 20,
    "Socia": 10,
}


# --- App factory y configuracion --------------------------------------------
def create_app():
    app = Flask(__name__)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
    app.secret_key = os.getenv("VANITY_HQ_SECRET_KEY", "dev-secret-change-me")
    app.permanent_session_lifetime = timedelta(days=7)

    @app.before_request
    def before_request():
        g.db = get_db()
        g.user = current_user()

    @app.teardown_appcontext
    def close_db(error=None):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    register_routes(app)
    init_db()
    return app


# --- Base de datos: conexion e inicializacion -------------------------------
def get_db():
    INSTANCE_DIR.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# --- Schema: crea tablas, seed de roles y usuarios por defecto --------------
def init_db():
    INSTANCE_DIR.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            level INTEGER NOT NULL,
            description TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            phone TEXT DEFAULT '',
            branch TEXT DEFAULT 'all',
            role_id INTEGER NOT NULL,
            theme TEXT DEFAULT 'system',
            is_active INTEGER DEFAULT 1,
            last_login TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(role_id) REFERENCES roles(id)
        );

        CREATE TABLE IF NOT EXISTS permissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_type TEXT NOT NULL,
            subject_id INTEGER NOT NULL,
            system TEXT NOT NULL,
            module TEXT NOT NULL,
            action TEXT NOT NULL,
            scope TEXT NOT NULL DEFAULT 'none',
            allowed INTEGER NOT NULL DEFAULT 0,
            UNIQUE(subject_type, subject_id, system, module, action)
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            actor_user_id INTEGER,
            action TEXT NOT NULL,
            target_type TEXT NOT NULL,
            target_id TEXT,
            detail TEXT DEFAULT '',
            created_at TEXT NOT NULL
        );
        """
    )

    for role_name, level in ROLE_LEVELS.items():
        cur.execute(
            "INSERT OR IGNORE INTO roles (name, level, description) VALUES (?, ?, ?)",
            (role_name, level, f"Rol base {role_name}"),
        )

    owner = cur.execute("SELECT id FROM roles WHERE name = 'Owner'").fetchone()
    admin_exists = cur.execute("SELECT id FROM users WHERE email = ?", ("admin@vanity.local",)).fetchone()
    now = datetime.utcnow().isoformat()
    if not admin_exists:
        cur.execute(
            """
            INSERT INTO users (name, email, username, password_hash, role_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "Admin Vanity",
                "admin@vanity.local",
                "admin",
                generate_password_hash("VanityAdmin2026!"),
                owner["id"],
                now,
                now,
            ),
        )

    for user_data in [
        ("Marco", "marco@soul23.mx", "marco", "Vanity2026!"),
        ("Ale", "ale@soul23.mx", "ale", "Vanity2026!"),
    ]:
        exists = cur.execute("SELECT id FROM users WHERE email = ?", (user_data[1],)).fetchone()
        if not exists:
            cur.execute(
                "INSERT INTO users (name, email, username, password_hash, role_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (user_data[0], user_data[1], user_data[2], generate_password_hash(user_data[3]), owner["id"], now, now),
            )

    seed_role_permissions(cur)
    conn.commit()
    conn.close()


# --- Seed: permisos por defecto para cada rol/sistema/modulo/accion ----------
def seed_role_permissions(cur):
    roles = {row["name"]: row["id"] for row in cur.execute("SELECT id, name FROM roles").fetchall()}
    for role_name, role_id in roles.items():
        for system_key, system in SYSTEMS.items():
            for module in system["modules"]:
                for action in ACTIONS:
                    allowed, scope = default_permission(role_name, system_key, module, action)
                    cur.execute(
                        """
                        INSERT OR IGNORE INTO permissions
                        (subject_type, subject_id, system, module, action, scope, allowed)
                        VALUES ('role', ?, ?, ?, ?, ?, ?)
                        """,
                        (role_id, system_key, module, action, scope, 1 if allowed else 0),
                    )


# --- Logica de permisos: Owner todo, Admin casi todo, Manager por sucursal, etc. ---
def default_permission(role, system, module, action):
    if role == "Owner":
        return True, "all"
    if role == "Admin":
        if system == "vanity_hq" and action in {"delete"}:
            return False, "none"
        return action in {"view", "create", "edit", "approve", "reject", "export", "import", "archive", "restore", "configure"}, "all"
    if role == "Manager":
        if system == "vanity_hq":
            return action == "view" and module in {"systems"}, "branch"
        if system == "vanity_hrmgr":
            return action in {"view", "create", "edit", "approve", "reject", "export"}, "branch"
        if system == "vanity_dashboard":
            return action in {"view", "export"}, "branch"
        if system == "vanity_payroll":
            return action == "view", "branch"
    if role == "Operador":
        return action in {"view", "create", "edit"} and module not in {"settings", "permissions", "roles"}, "assigned"
    if role == "Solo lectura":
        return action == "view", "assigned"
    if role == "Socia":
        own_modules = {"requests", "documents", "receipts", "history", "payments"}
        return action in {"view", "create"} and module in own_modules, "own"
    return False, "none"


# --- Autenticacion: sesion y helpers -----------------------------------------
def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return g.db.execute(
        """
        SELECT users.*, roles.name AS role_name, roles.level AS role_level
        FROM users JOIN roles ON users.role_id = roles.id
        WHERE users.id = ? AND users.is_active = 1
        """,
        (user_id,),
    ).fetchone()


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not g.user:
            return redirect(url_for("login", next=request.path))
        return fn(*args, **kwargs)

    return wrapper


def require_permission(system, module, action):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not g.user:
                return redirect(url_for("login", next=request.path))
            if not has_permission(g.user, system, module, action):
                flash("No tienes permiso para esa accion.", "warning")
                return redirect(url_for("hq"))
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def has_permission(user, system, module, action):
    role_perm = g.db.execute(
        """
        SELECT allowed FROM permissions
        WHERE subject_type = 'role' AND subject_id = ? AND system = ? AND module = ? AND action = ?
        """,
        (user["role_id"], system, module, action),
    ).fetchone()
    user_perm = g.db.execute(
        """
        SELECT allowed FROM permissions
        WHERE subject_type = 'user' AND subject_id = ? AND system = ? AND module = ? AND action = ?
        """,
        (user["id"], system, module, action),
    ).fetchone()
    if user_perm is not None:
        return bool(user_perm["allowed"])
    return bool(role_perm and role_perm["allowed"])


def get_permissions_for_user(user):
    rows = g.db.execute(
        """
        SELECT p.system, p.module, p.action, p.scope, p.allowed
        FROM permissions p
        WHERE p.subject_type = 'role' AND p.subject_id = ?
        ORDER BY p.system, p.module, p.action
        """,
        (user["role_id"],),
    ).fetchall()
    overrides = {
        (row["system"], row["module"], row["action"]): row
        for row in g.db.execute(
            """
            SELECT system, module, action, scope, allowed
            FROM permissions
            WHERE subject_type = 'user' AND subject_id = ?
            """,
            (user["id"],),
        ).fetchall()
    }
    permissions = []
    for row in rows:
        key = (row["system"], row["module"], row["action"])
        effective = overrides.get(key, row)
        if effective["allowed"]:
            permissions.append(
                {
                    "system": effective["system"],
                    "module": effective["module"],
                    "action": effective["action"],
                    "scope": effective["scope"],
                }
            )
    return permissions


def context_for_user(user):
    systems = allowed_systems(user)
    return {
        "user": {
            "id": user["id"],
            "name": user["name"],
            "email": user["email"],
            "username": user["username"],
            "role": user["role_name"],
            "level": user["role_level"],
            "branch": user["branch"],
        },
        "theme": user["theme"],
        "systems": [{"key": key, **value} for key, value in systems.items()],
        "permissions": get_permissions_for_user(user),
    }


def allowed_systems(user):
    permissions = get_permissions_for_user(user)
    visible = {p["system"] for p in permissions if p["action"] == "view"}
    return {key: value for key, value in SYSTEMS.items() if key in visible}


def audit(action, target_type, target_id="", detail=""):
    g.db.execute(
        """
        INSERT INTO audit_log (actor_user_id, action, target_type, target_id, detail, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (g.user["id"] if g.user else None, action, target_type, str(target_id), detail, datetime.utcnow().isoformat()),
    )
    g.db.commit()


# --- SSO Token: emision y validacion -----------------------------------------
def token_serializer():
    return URLSafeTimedSerializer(current_app_secret(), salt="vanity-hq-app-token")


def current_app_secret():
    return os.getenv("VANITY_HQ_SECRET_KEY", "dev-secret-change-me")


def issue_app_token(user, system):
    context = context_for_user(user)
    system_permissions = [permission for permission in context["permissions"] if permission["system"] == system]
    return token_serializer().dumps(
        {
            "user_id": user["id"],
            "system": system,
            "context": {
                "user": context["user"],
                "theme": context["theme"],
                "permissions": system_permissions,
            },
        }
    )


def validate_app_token(token, expected_system=None):
    data = token_serializer().loads(token, max_age=TOKEN_MAX_AGE)
    if expected_system and data.get("system") != expected_system:
        raise BadSignature("system mismatch")
    user = g.db.execute(
        """
        SELECT users.*, roles.name AS role_name, roles.level AS role_level
        FROM users JOIN roles ON users.role_id = roles.id
        WHERE users.id = ? AND users.is_active = 1
        """,
        (data["user_id"],),
    ).fetchone()
    if not user:
        raise BadSignature("user not found")
    return user, data


# --- Rutas -------------------------------------------------------------------
def register_routes(app):
    @app.route("/")
    def index():
        return redirect(url_for("hq") if g.user else url_for("login"))

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            identity = request.form.get("identity", "").strip().lower()
            password = request.form.get("password", "")
            remember = bool(request.form.get("remember"))
            user = g.db.execute(
                """
                SELECT users.*, roles.name AS role_name, roles.level AS role_level
                FROM users JOIN roles ON users.role_id = roles.id
                WHERE (LOWER(email) = ? OR LOWER(username) = ?) AND is_active = 1
                """,
                (identity, identity),
            ).fetchone()
            if user and check_password_hash(user["password_hash"], password):
                session.clear()
                session.permanent = remember
                session["user_id"] = user["id"]
                g.db.execute("UPDATE users SET last_login = ? WHERE id = ?", (datetime.utcnow().isoformat(), user["id"]))
                g.db.commit()
                return redirect(request.args.get("next") or url_for("hq"))
            flash("Credenciales incorrectas.", "danger")
        return render_template("login.html")

    @app.route("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))

    @app.route("/auth/hq")
    def auth_hq():
        token = request.args.get("token")
        if not token:
            flash("Token faltante.", "danger")
            return redirect(url_for("login"))

        try:
            user, token_data = validate_app_token(token, expected_system="hq")
        except:
            flash("Token inválido o expirado.", "danger")
            return redirect(url_for("login"))

        if token_data.get("system") != "hq":
            flash("Token no válido para este sistema.", "danger")
            return redirect(url_for("login"))

        # Set user session
        session["user_id"] = user["id"]
        session.permanent = True

        return redirect(url_for("hq"))

    @app.route("/hq")
    @login_required
    def hq():
        systems = allowed_systems(g.user)
        users_count = g.db.execute("SELECT COUNT(*) AS count FROM users").fetchone()["count"]
        audit_count = g.db.execute("SELECT COUNT(*) AS count FROM audit_log").fetchone()["count"]
        permissions_count = g.db.execute("SELECT COUNT(*) AS count FROM permissions WHERE allowed = 1").fetchone()["count"]
        return render_template(
            "hq.html",
            systems=systems,
            users_count=users_count,
            audit_count=audit_count,
            permissions_count=permissions_count,
        )

    @app.route("/healthz")
    def healthz():
        return jsonify({"ok": True, "service": "hq-wrapper"})

    @app.route("/launch/<system_key>")
    @login_required
    def launch_system(system_key):
        if system_key not in SYSTEMS:
            flash("Sistema no configurado.", "warning")
            return redirect(url_for("hq"))
        if not any(p["system"] == system_key and p["action"] == "view" for p in get_permissions_for_user(g.user)):
            flash("No tienes acceso a ese sistema.", "warning")
            return redirect(url_for("hq"))
        token = issue_app_token(g.user, system_key)
        base_url = SYSTEMS[system_key]["url"]
        if base_url.startswith("/"):
            return redirect(base_url)
        separator = "&" if "?" in base_url else "?"
        audit("launch", "system", system_key, f"Abrio {system_key}")
        return redirect(f"{base_url}/auth/hq{separator}token={token}")

    @app.route("/users")
    @require_permission("vanity_hq", "users", "view")
    def users():
        per_page = int(request.args.get("per_page", "50"))
        page = max(1, int(request.args.get("page", "1")))
        search = request.args.get("search", "").strip()
        role_filter = request.args.get("role", "").strip()
        status_filter = request.args.get("status", "").strip()

        where = []
        params = []
        if search:
            where.append("(users.name LIKE ? OR users.username LIKE ? OR users.email LIKE ?)")
            s = f"%{search}%"
            params.extend([s, s, s])
        if role_filter:
            where.append("users.role_id = ?")
            params.append(role_filter)
        if status_filter == "active":
            where.append("users.is_active = 1")
        elif status_filter == "inactive":
            where.append("users.is_active = 0")

        where_clause = ("WHERE " + " AND ".join(where)) if where else ""

        total = g.db.execute(
            f"SELECT COUNT(*) FROM users JOIN roles ON users.role_id = roles.id {where_clause}",
            params,
        ).fetchone()[0]
        total_pages = max(1, (total + per_page - 1) // per_page)
        offset = (page - 1) * per_page

        rows = g.db.execute(
            f"""
            SELECT users.*, roles.name AS role_name
            FROM users JOIN roles ON users.role_id = roles.id
            {where_clause}
            ORDER BY users.is_active DESC, users.name
            LIMIT ? OFFSET ?
            """,
            params + [per_page, offset],
        ).fetchall()
        roles = g.db.execute("SELECT * FROM roles ORDER BY level DESC").fetchall()
        return render_template(
            "users.html", users=rows, roles=roles,
            total=total, page=page, total_pages=total_pages, per_page=per_page,
            search=search, role_filter=role_filter, status_filter=status_filter,
        )

    @app.route("/users/new", methods=["POST"])
    @require_permission("vanity_hq", "users", "create")
    def create_user():
        now = datetime.utcnow().isoformat()
        g.db.execute(
            """
            INSERT INTO users (name, email, username, password_hash, phone, branch, role_id, theme, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                request.form["name"].strip(),
                request.form["email"].strip().lower(),
                request.form["username"].strip().lower(),
                generate_password_hash(request.form["password"]),
                request.form.get("phone", "").strip(),
                request.form.get("branch", "all").strip() or "all",
                request.form["role_id"],
                request.form.get("theme", "system"),
                now,
                now,
            ),
        )
        g.db.commit()
        audit("create", "user", request.form["email"], "Usuario creado")
        flash("Usuario creado.", "success")
        return redirect(url_for("users"))

    @app.route("/users/<int:user_id>/edit", methods=["POST"])
    @require_permission("vanity_hq", "users", "edit")
    def edit_user(user_id):
        values = [
            request.form["name"].strip(),
            request.form["email"].strip().lower(),
            request.form["username"].strip().lower(),
            request.form.get("phone", "").strip(),
            request.form.get("branch", "all").strip() or "all",
            request.form["role_id"],
            request.form.get("theme", "system"),
            1 if request.form.get("is_active") else 0,
            datetime.utcnow().isoformat(),
            user_id,
        ]
        g.db.execute(
            """
            UPDATE users
            SET name = ?, email = ?, username = ?, phone = ?, branch = ?, role_id = ?, theme = ?, is_active = ?, updated_at = ?
            WHERE id = ?
            """,
            values,
        )
        if request.form.get("password"):
            g.db.execute("UPDATE users SET password_hash = ? WHERE id = ?", (generate_password_hash(request.form["password"]), user_id))
        g.db.commit()
        audit("edit", "user", user_id, "Usuario actualizado")
        flash("Usuario actualizado.", "success")
        return redirect(url_for("users"))

    @app.route("/permissions", methods=["GET", "POST"])
    @require_permission("vanity_hq", "permissions", "view")
    def permissions():
        roles = g.db.execute("SELECT * FROM roles ORDER BY level DESC").fetchall()
        role_id = int(request.values.get("role_id") or roles[0]["id"])
        if request.method == "POST":
            if not has_permission(g.user, "vanity_hq", "permissions", "edit"):
                flash("No tienes permiso para editar permisos.", "warning")
                return redirect(url_for("permissions", role_id=role_id))
            g.db.execute("DELETE FROM permissions WHERE subject_type = 'role' AND subject_id = ?", (role_id,))
            for system_key, system in SYSTEMS.items():
                for module in system["modules"]:
                    for action in ACTIONS:
                        field = f"{system_key}.{module}.{action}"
                        allowed = 1 if request.form.get(field) else 0
                        scope = request.form.get(f"{field}.scope", "none")
                        g.db.execute(
                            """
                            INSERT INTO permissions (subject_type, subject_id, system, module, action, scope, allowed)
                            VALUES ('role', ?, ?, ?, ?, ?, ?)
                            """,
                            (role_id, system_key, module, action, scope, allowed),
                        )
            g.db.commit()
            audit("edit", "permissions", role_id, "Permisos de rol actualizados")
            flash("Permisos actualizados.", "success")
            return redirect(url_for("permissions", role_id=role_id))
        rows = g.db.execute(
            "SELECT * FROM permissions WHERE subject_type = 'role' AND subject_id = ?",
            (role_id,),
        ).fetchall()
        matrix = {(row["system"], row["module"], row["action"]): row for row in rows}
        role_name = next((r["name"] for r in roles if r["id"] == role_id), "")
        return render_template("permissions.html", roles=roles, role_id=role_id, role_name=role_name, systems=SYSTEMS, actions=ACTIONS, scopes=SCOPES, matrix=matrix)

    @app.route("/audit")
    @require_permission("vanity_hq", "audit", "view")
    def audit_view():
        per_page = int(request.args.get("per_page", "50"))
        page = max(1, int(request.args.get("page", "1")))
        search = request.args.get("search", "").strip()
        action_filter = request.args.get("action", "").strip()
        date_from = request.args.get("date_from", "").strip()
        date_to = request.args.get("date_to", "").strip()

        where = []
        params = []
        if search:
            where.append("(users.name LIKE ? OR audit_log.detail LIKE ?)")
            s = f"%{search}%"
            params.extend([s, s])
        if action_filter:
            where.append("audit_log.action = ?")
            params.append(action_filter)
        if date_from:
            where.append("audit_log.created_at >= ?")
            params.append(date_from)
        if date_to:
            where.append("audit_log.created_at <= ?")
            params.append(date_to + "T23:59:59")

        where_clause = ("WHERE " + " AND ".join(where)) if where else ""

        total = g.db.execute(
            f"SELECT COUNT(*) FROM audit_log LEFT JOIN users ON audit_log.actor_user_id = users.id {where_clause}",
            params,
        ).fetchone()[0]
        total_pages = max(1, (total + per_page - 1) // per_page)
        offset = (page - 1) * per_page

        rows = g.db.execute(
            f"""
            SELECT audit_log.*, users.name AS actor_name
            FROM audit_log LEFT JOIN users ON audit_log.actor_user_id = users.id
            {where_clause}
            ORDER BY audit_log.created_at DESC
            LIMIT ? OFFSET ?
            """,
            params + [per_page, offset],
        ).fetchall()

        actions = g.db.execute(
            "SELECT DISTINCT action FROM audit_log ORDER BY action"
        ).fetchall()

        return render_template(
            "audit.html", rows=rows,
            total=total, page=page, total_pages=total_pages, per_page=per_page,
            search=search, action_filter=action_filter,
            date_from=date_from, date_to=date_to,
            actions=[a["action"] for a in actions],
        )

    @app.route("/profile", methods=["GET", "POST"])
    @login_required
    def profile():
        if request.method == "POST":
            g.db.execute(
                "UPDATE users SET name = ?, theme = ?, updated_at = ? WHERE id = ?",
                (request.form["name"].strip(), request.form.get("theme", "system"), datetime.utcnow().isoformat(), g.user["id"]),
            )
            if request.form.get("password"):
                g.db.execute("UPDATE users SET password_hash = ? WHERE id = ?", (generate_password_hash(request.form["password"]), g.user["id"]))
            g.db.commit()
            session["user_id"] = g.user["id"]
            flash("Perfil actualizado.", "success")
            return redirect(url_for("profile"))
        return render_template("profile.html")

    @app.route("/api/context/me")
    @login_required
    def context_me():
        return jsonify(context_for_user(g.user))

    @app.route("/api/auth/validate-token", methods=["POST"])
    def validate_token_api():
        payload = request.get_json(silent=True) or {}
        token = payload.get("token") or request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        expected_system = payload.get("system")
        if not token:
            return jsonify({"ok": False, "error": "missing token"}), 400
        try:
            user, token_data = validate_app_token(token, expected_system)
        except SignatureExpired:
            return jsonify({"ok": False, "error": "expired token"}), 401
        except BadSignature:
            return jsonify({"ok": False, "error": "invalid token"}), 401
        return jsonify({"ok": True, "system": token_data["system"], "context": context_for_user(user)})

    @app.route("/api/permissions/effective")
    @login_required
    def effective_permissions_api():
        return jsonify({"permissions": get_permissions_for_user(g.user)})

    @app.route("/api/permissions/check", methods=["POST"])
    @login_required
    def check_permission_api():
        payload = request.get_json(silent=True) or {}
        allowed = has_permission(
            g.user,
            payload.get("system", ""),
            payload.get("module", ""),
            payload.get("action", ""),
        )
        return jsonify({"allowed": allowed})

    @app.route("/api/audit/events", methods=["POST"])
    def audit_events_api():
        payload = request.get_json(silent=True) or {}
        token = payload.get("token") or request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        if not token:
            return jsonify({"ok": False, "error": "missing token"}), 400
        try:
            user, token_data = validate_app_token(token, payload.get("system"))
        except SignatureExpired:
            return jsonify({"ok": False, "error": "expired token"}), 401
        except BadSignature:
            return jsonify({"ok": False, "error": "invalid token"}), 401
        g.db.execute(
            """
            INSERT INTO audit_log (actor_user_id, action, target_type, target_id, detail, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                user["id"],
                payload.get("action", "event"),
                f"{token_data['system']}:{payload.get('target_type', 'unknown')}",
                str(payload.get("target_id", "")),
                payload.get("detail", ""),
                datetime.utcnow().isoformat(),
            ),
        )
        g.db.commit()
        return jsonify({"ok": True})


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.getenv("PORT", "5050")), debug=True)
