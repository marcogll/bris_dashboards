# =============================================================================
# Vanity EmpReq - Portal de Solicitudes de Empleadas
# =============================================================================
# Servicio Flask para solicitudes de vacaciones, permisos e incapacidades.
# Autenticacion SSO via HQ Wrapper (token URLSafeTimedSerializer).
# Base de datos: SQLite en instance/vanity_empreq.db
# Puerto: 5053 (default)
#
# Flujo SSO: mismo patron que Actas.
# Modulos de permisos: "requests", "settings"
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
DB_PATH = BASE_DIR / "instance" / "vanity_empreq.db"
HQ_BASE_URL = os.getenv("VANITY_HQ_URL", "http://127.0.0.1:5050")
HQ_PUBLIC_URL = os.getenv("VANITY_HQ_PUBLIC_URL", HQ_BASE_URL)
SYSTEM_KEY = "vanity_empreq"
HQ_SECRET_KEY = os.getenv("VANITY_HQ_SECRET_KEY", "dev-secret-change-me")
HQ_TOKEN_MAX_AGE = int(os.getenv("VANITY_HQ_TOKEN_MAX_AGE", "43200"))
serializer = URLSafeTimedSerializer(HQ_SECRET_KEY, salt="vanity-hq-app-token")


# --- App factory y hooks de request -----------------------------------------
def create_app():
    app = Flask(__name__)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
    app.secret_key = os.getenv("VANITY_EMPREQ_SECRET_KEY", "dev-empreq-secret")
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
    for permission in g.hq_context.get("permissions", []):
        if permission.get("system") == SYSTEM_KEY and permission.get("module") == module and permission.get("action") == action:
            return True
    return False


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not g.hq_context:
            return redirect(f"{HQ_PUBLIC_URL}/launch/{SYSTEM_KEY}")
        return fn(*args, **kwargs)
    return wrapper


def require_permission(module, action):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not g.hq_context:
                return redirect(f"{HQ_PUBLIC_URL}/launch/{SYSTEM_KEY}")
            if not has_permission(module, action):
                flash("No tienes permiso para esta accion.", "warning")
                return redirect(url_for("dashboard"))
            return fn(*args, **kwargs)
        return wrapper
    return decorator


# --- Auditoria: reenvia eventos al HQ Wrapper --------------------------------
def audit_hq(action, target_type, target_id="", detail=""):
    if not g.hq_token:
        return
    payload = json.dumps({
        "token": g.hq_token,
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
        audit_hq("login", "session", context["user"]["id"], "Ingreso a EmpReq")
        return redirect(url_for("dashboard"))

    @app.route("/dashboard")
    @login_required
    def dashboard():
        total = scalar("SELECT COUNT(*) FROM solicitudes")
        pendientes = scalar("SELECT COUNT(*) FROM solicitudes WHERE status = 'pendiente'")
        aprobadas = scalar("SELECT COUNT(*) FROM solicitudes WHERE status = 'aprobada'")
        types = g.db.execute(
            "SELECT request_type, COUNT(*) AS c FROM solicitudes GROUP BY request_type ORDER BY c DESC"
        ).fetchall()
        return render_template("dashboard.html", total=total, pendientes=pendientes,
                               aprobadas=aprobadas, types=types)

    @app.route("/healthz")
    def healthz():
        return jsonify({"ok": True, "service": "empreq"})

    @app.route("/manifest.json")
    def manifest():
        return render_template("manifest.json"), 200, {"Content-Type": "application/json"}

    @app.route("/service-worker.js")
    def service_worker():
        return render_template("service-worker.js"), 200, {"Content-Type": "application/javascript"}

    @app.route("/solicitudes")
    @require_permission("requests", "view")
    def solicitudes_list():
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
            where.append("request_type = ?")
            params.append(type_filter)
        if status_filter:
            where.append("status = ?")
            params.append(status_filter)

        base_sql = "FROM solicitudes"
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

        request_types = g.db.execute("SELECT * FROM request_types ORDER BY label").fetchall()
        return render_template("solicitudes_list.html", rows=rows, request_types=request_types,
                               search=search, type_filter=type_filter, status_filter=status_filter,
                               page=page, total_pages=total_pages, total=total, per_page=PER_PAGE)

    @app.route("/solicitudes/<int:solicitud_id>")
    @require_permission("requests", "view")
    def solicitud_detail(solicitud_id):
        solicitud = g.db.execute("SELECT * FROM solicitudes WHERE id = ?", (solicitud_id,)).fetchone()
        if not solicitud:
            flash("Solicitud no encontrada.", "danger")
            return redirect(url_for("solicitudes_list"))
        return render_template("solicitud_detail.html", solicitud=solicitud)

    @app.route("/solicitudes/nueva", methods=["GET", "POST"])
    @require_permission("requests", "create")
    def solicitud_nueva():
        if request.method == "POST":
            now = datetime.utcnow().isoformat()
            employee_name = request.form["employee_name"].strip()
            g.db.execute(
                """
                INSERT INTO solicitudes (employee_name, employee_id, request_type, description, start_date, end_date, status, created_by, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, 'pendiente', ?, ?, ?)
                """,
                (
                    employee_name,
                    request.form.get("employee_id", "").strip(),
                    request.form["request_type"],
                    request.form["description"].strip(),
                    request.form.get("start_date", ""),
                    request.form.get("end_date", ""),
                    (g.hq_context or {}).get("user", {}).get("name", ""),
                    now, now,
                ),
            )
            g.db.commit()
            audit_hq("create", "solicitud", employee_name, "Solicitud creada")
            flash("Solicitud registrada.", "success")
            return redirect(url_for("solicitudes_list"))

        request_types = g.db.execute("SELECT * FROM request_types ORDER BY label").fetchall()
        return render_template("solicitud_form.html", request_types=request_types, solicitud=None)

    @app.route("/solicitudes/<int:solicitud_id>/editar", methods=["GET", "POST"])
    @require_permission("requests", "edit")
    def solicitud_editar(solicitud_id):
        solicitud = g.db.execute("SELECT * FROM solicitudes WHERE id = ?", (solicitud_id,)).fetchone()
        if not solicitud:
            flash("Solicitud no encontrada.", "danger")
            return redirect(url_for("solicitudes_list"))

        if request.method == "POST":
            now = datetime.utcnow().isoformat()
            g.db.execute(
                """
                UPDATE solicitudes SET employee_name = ?, employee_id = ?, request_type = ?, description = ?, start_date = ?, end_date = ?, status = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    request.form["employee_name"].strip(),
                    request.form.get("employee_id", "").strip(),
                    request.form["request_type"],
                    request.form["description"].strip(),
                    request.form.get("start_date", ""),
                    request.form.get("end_date", ""),
                    request.form["status"],
                    now, solicitud_id,
                ),
            )
            g.db.commit()
            audit_hq("edit", "solicitud", solicitud_id, "Solicitud editada")
            flash("Solicitud actualizada.", "success")
            return redirect(url_for("solicitud_detail", solicitud_id=solicitud_id))

        request_types = g.db.execute("SELECT * FROM request_types ORDER BY label").fetchall()
        return render_template("solicitud_form.html", request_types=request_types, solicitud=solicitud)

    @app.route("/solicitudes/<int:solicitud_id>/eliminar", methods=["POST"])
    @require_permission("requests", "delete")
    def solicitud_eliminar(solicitud_id):
        solicitud = g.db.execute("SELECT id FROM solicitudes WHERE id = ?", (solicitud_id,)).fetchone()
        if not solicitud:
            flash("Solicitud no encontrada.", "danger")
            return redirect(url_for("solicitudes_list"))
        g.db.execute("DELETE FROM solicitudes WHERE id = ?", (solicitud_id,))
        g.db.commit()
        audit_hq("delete", "solicitud", solicitud_id, "Solicitud eliminada")
        flash("Solicitud eliminada.", "success")
        return redirect(url_for("solicitudes_list"))


def scalar(query, params=()):
    return g.db.execute(query, params).fetchone()[0]


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5053))
    app.run(debug=True, host="0.0.0.0", port=port)
