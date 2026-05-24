# =============================================================================
# Vanity Actas - Registro de Actas Administrativas
# =============================================================================
# Servicio Flask para CRUD de actas (faltas, retardos, sanciones).
# Autenticacion SSO via HQ Wrapper (token URLSafeTimedSerializer).
# Base de datos: SQLite en instance/vanity_actas.db
# Puertos: 5052 (default)
#
# Flujo SSO:
#   1. HQ Wrapper lanza token en /launch/vanity_actas
#   2. Este servicio recibe token en /auth/hq?token=...
#   3. Valida localmente con VANITY_HQ_SECRET_KEY, fallback a HQ API
#   4. Contexto (usuario, permisos) se guarda en session
#
# Modulos de permisos: "actas", "settings"
# Acciones: view, create, edit, delete
# =============================================================================

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime
from functools import wraps
from pathlib import Path

_common_dir = Path(__file__).resolve().parent
if not (_common_dir / "vanity_common").is_dir():
    _common_dir = _common_dir.parent
sys.path.insert(0, str(_common_dir))

from vanity_common.auth import load_user_from_session
from vanity_common.session import SupabaseSessionInterface

from flask import Flask, flash, g, jsonify, redirect, render_template, request, session, url_for
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.middleware.proxy_fix import ProxyFix

from scripts.db import connect, init_db

# --- Configuracion y constantes -----------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "instance" / "vanity_actas.db"
HQ_BASE_URL = os.getenv("VANITY_HQ_URL", "http://127.0.0.1:5050")
HQ_PUBLIC_URL = os.getenv("VANITY_HQ_PUBLIC_URL", HQ_BASE_URL)
SYSTEM_KEY = "vanity_actas"
HQ_SECRET_KEY = os.getenv("VANITY_HQ_SECRET_KEY", "dev-secret-change-me")
HQ_TOKEN_MAX_AGE = int(os.getenv("VANITY_HQ_TOKEN_MAX_AGE", "43200"))


# --- App factory y hooks de request -----------------------------------------
def create_app():
    app = Flask(__name__)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
    app.secret_key = os.getenv("VANITY_ACTAS_SECRET_KEY", "dev-actas-secret")
    app.config["TEMPLATES_AUTO_RELOAD"] = True
    app.config["VANITY_HQ_PUBLIC_URL"] = os.getenv("VANITY_HQ_PUBLIC_URL", HQ_PUBLIC_URL)
    app.config["VANITY_HQ_SECRET_KEY"] = HQ_SECRET_KEY
    app.config["VANITY_HQ_URL"] = HQ_BASE_URL
    app.session_interface = SupabaseSessionInterface()

    @app.before_request
    def before_request():
        g.db = connect(DB_PATH)
        g.hq_context = session.get("hq_context")
        g.hq_token = session.get("hq_token")
        load_user_from_session()

    @app.teardown_appcontext
    def close_db(error=None):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    @app.context_processor
    def inject_hq_helpers():
        return {"can": has_permission, "hq_user": lambda: (g.hq_context or {}).get("user", {})}

    register_routes(app)
    with connect(DB_PATH) as conn:
        init_db(conn)
    return app


# --- SSO Token: validacion local + fallback a HQ API -------------------------
def validate_hq_token(token):
    try:
        data = serializer.loads(token, max_age=HQ_TOKEN_MAX_AGE)
        if data.get("system") != SYSTEM_KEY:
            raise ValueError("system mismatch")
        if data.get("context"):
            return data["context"]
    except (BadSignature, SignatureExpired, ValueError):
        raise

    payload = json.dumps({"token": token, "system": SYSTEM_KEY}).encode()
    req = urllib.request.Request(
        f"{HQ_BASE_URL}/api/auth/validate-token",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as response:
        data = json.loads(response.read().decode())
    if not data.get("ok"):
        raise ValueError(data.get("error", "invalid token"))
    return data["context"]


# --- Permisos y decoradores de autenticacion ----------------------------------
def has_permission(module, action):
    for permission in context.get("permissions", []):
        if permission.get("system") == SYSTEM_KEY and permission.get("module") == module and permission.get("action") == action:
            return True
    return False


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not g.hq_context:
            return redirect(f"{HQ_BASE_URL}/launch/{SYSTEM_KEY}")
        return fn(*args, **kwargs)
    return wrapper


def require_permission(module, action):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not g.hq_context:
                return redirect(f"{HQ_BASE_URL}/launch/{SYSTEM_KEY}")
            if not has_permission(module, action):
                flash("No tienes permiso para esta accion.", "warning")
                return redirect(url_for("dashboard"))
            return fn(*args, **kwargs)
        return wrapper
    return decorator


# --- Auditoria: reenvia eventos al HQ Wrapper --------------------------------
def audit_hq(action, target_type, target_id="", detail=""):
    if not hq_token:
        return
    payload = json.dumps({
        "token": hq_token,
        "system": SYSTEM_KEY,
        "action": action,
        "target_type": target_type,
        "target_id": str(target_id),
        "detail": detail,
    }).encode()
    req = urllib.request.Request(
        f"{HQ_BASE_URL}/api/audit/events",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=3).read()
    except (urllib.error.URLError, TimeoutError):
        pass


# --- Rutas -------------------------------------------------------------------
def register_routes(app):

    @app.route("/")
    def index():
        return redirect(url_for("dashboard"))

    @app.route("/login")
    def login():
        return redirect(f"{HQ_PUBLIC_URL}/launch/{SYSTEM_KEY}")

    @app.route("/logout")
    def logout():
        session.clear()
        return redirect(f"{HQ_PUBLIC_URL}/hq")

    @app.route("/auth/hq")
    def auth_hq():
        token = request.args.get("token", "")
        if not token:
            flash("Token HQ faltante.", "danger")
            return redirect(f"{HQ_PUBLIC_URL}/hq")
        try:
            context = validate_hq_token(token)
        except Exception:
            flash("No se pudo validar la sesion HQ.", "danger")
            return redirect(f"{HQ_PUBLIC_URL}/hq")
        session["hq_token"] = token
        session["hq_context"] = context
        audit_hq("login", "session", context["user"]["id"], "Ingreso a Actas")
        return redirect(url_for("dashboard"))

    @app.route("/dashboard")
    @login_required
    def dashboard():
        total = scalar("SELECT COUNT(*) FROM actas")
        pendientes = scalar("SELECT COUNT(*) FROM actas WHERE status = 'pendiente'")
        completadas = scalar("SELECT COUNT(*) FROM actas WHERE status = 'completada'")
        types = g.db.execute(
            "SELECT acta_type, COUNT(*) AS c FROM actas GROUP BY acta_type ORDER BY c DESC"
        ).fetchall()
        return render_template("dashboard.html", total=total, pendientes=pendientes,
                               completadas=completadas, types=types)

    @app.route("/healthz")
    def healthz():
        return jsonify({"ok": True, "service": "actas"})

    @app.route("/actas")
    @require_permission("actas", "view")
    def actas_list():
        PER_PAGE = 50
        page = int(request.args.get("page", 1))
        if page < 1:
            page = 1
        search = request.args.get("search", "").strip()
        type_filter = request.args.get("type", "").strip()
        status_filter = request.args.get("status", "").strip()

        where = []
        params = []
        if search:
            where.append("(employee_name LIKE ? OR description LIKE ?)")
            params.extend([f"%{search}%", f"%{search}%"])
        if type_filter:
            where.append("acta_type = ?")
            params.append(type_filter)
        if status_filter:
            where.append("status = ?")
            params.append(status_filter)

        base_sql = "FROM actas"
        if where:
            base_sql += " WHERE " + " AND ".join(where)

        total = scalar(f"SELECT COUNT(*) {base_sql}", params)
        total_pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)
        if page > total_pages:
            page = total_pages
        offset = (page - 1) * PER_PAGE

        rows = g.db.execute(
            f"SELECT * {base_sql} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params + [PER_PAGE, offset],
        ).fetchall()

        acta_types = g.db.execute("SELECT * FROM acta_types ORDER BY label").fetchall()
        return render_template("actas_list.html", rows=rows, acta_types=acta_types,
                               search=search, type_filter=type_filter, status_filter=status_filter,
                               page=page, total_pages=total_pages, total=total, per_page=PER_PAGE)

    @app.route("/actas/<int:acta_id>")
    @require_permission("actas", "view")
    def acta_detail(acta_id):
        acta = g.db.execute("SELECT * FROM actas WHERE id = ?", (acta_id,)).fetchone()
        if not acta:
            flash("Acta no encontrada.", "danger")
            return redirect(url_for("actas_list"))
        return render_template("acta_detail.html", acta=acta)

    @app.route("/actas/nueva", methods=["GET", "POST"])
    @require_permission("actas", "create")
    def acta_nueva():
        if request.method == "POST":
            now = datetime.utcnow().isoformat()
            employee_name = request.form["employee_name"].strip()
            g.db.execute(
                """
                INSERT INTO actas (employee_name, employee_id, acta_type, description, status, created_by, created_at, updated_at)
                VALUES (?, ?, ?, ?, 'pendiente', ?, ?, ?)
                """,
                (
                    employee_name,
                    request.form.get("employee_id", "").strip(),
                    request.form["acta_type"],
                    request.form["description"].strip(),
                    (g.hq_context or {}).get("user", {}).get("name", ""),
                    now, now,
                ),
            )
            g.db.commit()
            audit_hq("create", "acta", employee_name, "Acta creada")
            flash("Acta registrada.", "success")
            return redirect(url_for("actas_list"))

        acta_types = g.db.execute("SELECT * FROM acta_types ORDER BY label").fetchall()
        return render_template("acta_form.html", acta_types=acta_types, acta=None)

    @app.route("/actas/<int:acta_id>/editar", methods=["GET", "POST"])
    @require_permission("actas", "edit")
    def acta_editar(acta_id):
        acta = g.db.execute("SELECT * FROM actas WHERE id = ?", (acta_id,)).fetchone()
        if not acta:
            flash("Acta no encontrada.", "danger")
            return redirect(url_for("actas_list"))

        if request.method == "POST":
            now = datetime.utcnow().isoformat()
            g.db.execute(
                """
                UPDATE actas SET employee_name = ?, employee_id = ?, acta_type = ?, description = ?, status = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    request.form["employee_name"].strip(),
                    request.form.get("employee_id", "").strip(),
                    request.form["acta_type"],
                    request.form["description"].strip(),
                    request.form["status"],
                    now, acta_id,
                ),
            )
            g.db.commit()
            audit_hq("edit", "acta", acta_id, "Acta editada")
            flash("Acta actualizada.", "success")
            return redirect(url_for("acta_detail", acta_id=acta_id))

        acta_types = g.db.execute("SELECT * FROM acta_types ORDER BY label").fetchall()
        return render_template("acta_form.html", acta_types=acta_types, acta=acta)

    @app.route("/actas/<int:acta_id>/eliminar", methods=["POST"])
    @require_permission("actas", "delete")
    def acta_eliminar(acta_id):
        acta = g.db.execute("SELECT id FROM actas WHERE id = ?", (acta_id,)).fetchone()
        if not acta:
            flash("Acta no encontrada.", "danger")
            return redirect(url_for("actas_list"))
        g.db.execute("DELETE FROM actas WHERE id = ?", (acta_id,))
        g.db.commit()
        audit_hq("delete", "acta", acta_id, "Acta eliminada")
        flash("Acta eliminada.", "success")
        return redirect(url_for("actas_list"))


def scalar(query, params=()):
    return g.db.execute(query, params).fetchone()[0]


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5052))
    app.run(debug=True, host="0.0.0.0", port=port)
