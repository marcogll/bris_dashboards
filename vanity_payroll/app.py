# =============================================================================
# Vanity Payroll - Sistema de Nomina
# =============================================================================
# Servicio Flask para gestion de nomina, pagos, recibos e historial.
# Autenticacion SSO via HQ Wrapper con permisos RBAC por scope.
# Base de datos: SQLite en instance/vanity_payroll.db
# Puerto: 5051 (default)
#
# Flujo SSO: mismo patron que Actas/EmpReq, con extensiones:
#   - APIs service-to-service protegidas por VANITY_PAYROLL_API_TOKEN
#   - Visibilidad de datos por scope (all, branch, own)
#
# Esquemas de pago:
#   - Laboral: sueldo base (horas * 43.75) + comisiones por escalones
#   - Mercantil: 30% de utilidad neta
#
# Modulos de permisos: people, sales, periods, payments, receipts,
#   concepts, approvals, history, reports, settings
#
# Endpoints principales:
#   /auth/hq                      - SSO entry
#   /dashboard                     - Dashboard general
#   /people, /people/<id>          - CRUD personas
#   /payments, /payments/<id>      - Lista y detalle de pagos
#   /periods, /periods/<id>        - Periodos de nomina
#   /api/people/*, /api/receipts/* - APIs service-to-service
# =============================================================================

import json
import os
import secrets
import sys
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta
from functools import wraps
from pathlib import Path

_common_dir = Path(__file__).resolve().parent
if not (_common_dir / "vanity_common").is_dir():
    _common_dir = _common_dir.parent
sys.path.insert(0, str(_common_dir))

from vanity_common.auth import load_user_from_session
from vanity_common.session import SupabaseSessionInterface

from flask import Flask, abort, flash, g, jsonify, redirect, render_template, request, session, url_for, send_from_directory
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.middleware.proxy_fix import ProxyFix

from scripts.db import connect, init_db

# --- Configuracion y constantes -----------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "instance" / "vanity_payroll.db"
HQ_BASE_URL = os.getenv("VANITY_HQ_URL", "http://127.0.0.1:5050")
HQ_PUBLIC_URL = os.getenv("VANITY_HQ_PUBLIC_URL", HQ_BASE_URL)
SYSTEM_KEY = "vanity_payroll"
HQ_SECRET_KEY = os.getenv("VANITY_HQ_SECRET_KEY", "dev-secret-change-me")
HQ_TOKEN_MAX_AGE = int(os.getenv("VANITY_HQ_TOKEN_MAX_AGE", "43200"))
PAYROLL_API_TOKEN = os.getenv("VANITY_PAYROLL_API_TOKEN", "")


def create_app():
    app = Flask(__name__)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
    app.secret_key = os.getenv("VANITY_PAYROLL_SECRET_KEY", "dev-payroll-secret")
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE=os.getenv("SESSION_COOKIE_SAMESITE", "Lax"),
        SESSION_COOKIE_SECURE=os.getenv("SESSION_COOKIE_SECURE", "false").lower() in {"1", "true", "yes"},
        PERMANENT_SESSION_LIFETIME=timedelta(seconds=HQ_TOKEN_MAX_AGE),
    )
    app.config["VANITY_HQ_PUBLIC_URL"] = os.getenv("VANITY_HQ_PUBLIC_URL", HQ_PUBLIC_URL)
    app.config["VANITY_HQ_SECRET_KEY"] = HQ_SECRET_KEY
    app.config["VANITY_HQ_URL"] = HQ_BASE_URL
    app.session_interface = SupabaseSessionInterface()

    # --- CSRF protection y hooks de request ----------------------------------------
    @app.before_request
    def before_request():
        g.db = connect(DB_PATH)
        g.hq_context = session.get("hq_context")
        g.hq_token = session.get("hq_token")
        load_user_from_session()
        if request.method in {"POST", "PUT", "PATCH", "DELETE"} and not request.path.startswith("/api/"):
            submitted = request.form.get("_csrf_token") or request.headers.get("X-CSRF-Token", "")
            if not submitted or not secrets.compare_digest(submitted, session.get("_csrf_token", "")):
                abort(400, "invalid csrf token")

    @app.teardown_appcontext
    def close_db(error=None):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    @app.context_processor
    def inject_hq_helpers():
        return {
            "can": has_permission,
            "csrf_token": csrf_token,
            "hq_user": lambda: (g.hq_context or {}).get("user", {}),
        }

    register_routes(app)
    with connect(DB_PATH) as conn:
        init_db(conn)
    return app


# --- Funciones de utilidad y calculo de nomina --------------------------------
HOURLY_RATE = 43.75  # 2100 / 48


def money(value):
    return "${:,.2f}".format(value or 0)


def csrf_token():
    token = session.get("_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["_csrf_token"] = token
    return token


def mround(value, multiple=5):
    if not value:
        return 0.0
    return round(value / multiple) * multiple


def contract_rules(contract):
    if not contract or not contract["rules_json"]:
        return {}
    try:
        return json.loads(contract["rules_json"])
    except json.JSONDecodeError:
        return {}


def calculate_payment(person, contract, sales_total, actual_hours=None, bono_punt_eligible=True, bono_ext_eligible=True):
    rules = contract_rules(contract)
    contract_type = person["contract_type"]
    earnings = []
    deductions = []

    sched_hours = float(rules.get("scheduled_hours", 48))
    hours = actual_hours if actual_hours is not None else sched_hours
    fixed_pay = float(contract["base_salary"] if contract else 0)
    bono_punt_val = float(rules.get("punctuality_attendance_bonus", 0) or 0)
    bono_ext_val = float(rules.get("additional_bonus", 0) or 0)

    if contract_type == "laboral":
        base_pay = hours * HOURLY_RATE
        if base_pay:
            earnings.append(("HOURLY_PAY", f"Pago base ({hours}h x ${HOURLY_RATE}/hr)", base_pay))

        utility = sales_total * 0.7

        if utility >= 12000:
            comm_rate = float(rules.get("commission_cap_rate", 0.12) or 0.12)
        elif utility >= 10000:
            comm_rate = 0.08
        elif utility > 8000:
            comm_rate = 0.05
        else:
            comm_rate = 0.0

        commission = utility * comm_rate if comm_rate > 0 else 0.0
        if commission:
            earnings.append(("SALES_COMMISSION", f"Comision ({comm_rate*100:.0f}% sobre utilidad ${utility:,.2f})", commission))
    else:
        utility = sales_total * 0.7
        commission = utility * 0.30
        if commission:
            earnings.append(("SALES_COMMISSION", f"Comision mercantil (30% de utilidad ${utility:,.2f})", commission))

    if bono_punt_eligible and bono_punt_val:
        earnings.append(("PUNCTUALITY_BONUS", "Bono puntualidad", bono_punt_val))
    if bono_ext_eligible and bono_ext_val:
        earnings.append(("EXTRA_BONUS", "Bono extra", bono_ext_val))

    gross = sum(amount for _, _, amount in earnings)
    net = mround(gross)
    adjustment = round(net - gross, 2)

    if adjustment:
        earnings.append(("ADJUSTMENT", f"Ajuste redondeo (MROUND a 5)", adjustment))

    final_gross = sum(amount for _, _, amount in earnings)
    final_net = final_gross

    return final_gross, 0.0, final_net, earnings, deductions, {"fixed_pay": fixed_pay}


# --- SSO Token: validacion local + fallback a HQ API -------------------------
def validate_hq_token(token):
    serializer = URLSafeTimedSerializer(HQ_SECRET_KEY, salt="vanity-hq-app-token")
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


# --- Permisos y decoradores de autenticacion ------------------------------------
def has_permission(module, action):
    for permission in context.get("permissions", []):
        if permission.get("system") == SYSTEM_KEY and permission.get("module") == module and permission.get("action") == action:
            return True
    return False


def permission_scope(module, action, context=None):
    context = context or g.hq_context or {}
    for permission in context.get("permissions", []):
        if permission.get("system") == SYSTEM_KEY and permission.get("module") == module and permission.get("action") == action:
            return permission.get("scope", "none")
    return "none"


def current_actor_name():
    user = (g.hq_context or {}).get("user", {})
    return user.get("name") or user.get("email") or user.get("username") or "HQ"


# --- API auth: Bearer token para service-to-service ----------------------------
def bearer_token():
    header = request.headers.get("Authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    return ""


def api_auth_required(module="receipts", action="view"):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            token = bearer_token()
            if PAYROLL_API_TOKEN and secrets.compare_digest(token, PAYROLL_API_TOKEN):
                g.api_access = {"kind": "service", "scope": "all"}
                return fn(*args, **kwargs)
            if token:
                try:
                    context = validate_hq_token(token)
                except (BadSignature, SignatureExpired, ValueError, urllib.error.URLError, TimeoutError):
                    return jsonify({"ok": False, "error": "invalid token"}), 401
                g.hq_context = context
                g.api_access = {"kind": "hq", "scope": permission_scope(module, action, context)}
                if g.api_access["scope"] != "none":
                    return fn(*args, **kwargs)
            return jsonify({"ok": False, "error": "unauthorized"}), 401
        return wrapper
    return decorator


# --- Visibilidad de datos por scope (all/branch/own) ---------------------------
def person_visible_to_current_access(person, module="receipts", action="view"):
    access = getattr(g, "api_access", None)
    if access and access.get("kind") == "service":
        return True

    context = g.hq_context or {}
    scope = permission_scope(module, action, context)
    if scope == "all":
        return True
    user = context.get("user", {})
    if scope == "branch":
        return bool(user.get("branch")) and (person["branch_name"] or "") == user.get("branch")
    if scope == "own":
        return bool(user.get("email")) and (person["email"] or "").lower() == user.get("email", "").lower()
    return False


def person_visible_to_current_user(person, module, action):
    scope = permission_scope(module, action)
    if scope == "all":
        return True
    user = (g.hq_context or {}).get("user", {})
    if scope == "branch":
        return bool(user.get("branch")) and (person["branch_name"] or "") == user.get("branch")
    if scope == "own":
        return bool(user.get("email")) and (person["email"] or "").lower() == user.get("email", "").lower()
    return False


def require_visible_person(person, module, action):
    if not person_visible_to_current_user(person, module, action):
        abort(403)


def require_visible_payment(payment_id, module="payments", action="view"):
    person = g.db.execute(
        """
        SELECT people.*
        FROM payroll_payments
        JOIN people ON people.id = payroll_payments.person_id
        WHERE payroll_payments.id = ?
        """,
        (payment_id,),
    ).fetchone()
    if not person:
        abort(404)
    require_visible_person(person, module, action)
    return person


def scoped_people_clause(module, action, table_alias="people"):
    scope = permission_scope(module, action)
    user = (g.hq_context or {}).get("user", {})
    if scope == "all":
        return "", []
    if scope == "branch" and user.get("branch"):
        return f"{table_alias}.branch_name = ?", [user["branch"]]
    if scope == "own" and user.get("email"):
        return f"LOWER({table_alias}.email) = LOWER(?)", [user["email"]]
    return "1 = 0", []


def require_api_person_access(person_id, module="receipts", action="view"):
    person = g.db.execute("SELECT * FROM people WHERE id = ?", (person_id,)).fetchone()
    if not person:
        return None, (jsonify({"ok": False, "error": "not found"}), 404)
    if not person_visible_to_current_access(person, module, action):
        return None, (jsonify({"ok": False, "error": "forbidden"}), 403)
    return person, None


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
                abort(403)
            return fn(*args, **kwargs)

        return wrapper

    return decorator


# --- Auditoria: reenvia eventos al HQ Wrapper ---------------------------------
def audit_hq(action, target_type, target_id="", detail=""):
    if not hq_token:
        return
    payload = json.dumps(
        {
            "token": hq_token,
            "system": SYSTEM_KEY,
            "action": action,
            "target_type": target_type,
            "target_id": str(target_id),
            "detail": detail,
        }
    ).encode()
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
    app.jinja_env.filters["money"] = money

    @app.template_filter("from_json")
    def from_json_filter(value):
        if not value:
            return {}
        try:
            return json.loads(value) if isinstance(value, str) else value
        except (json.JSONDecodeError, TypeError):
            return {}

    # ------------------------------------------------------------------ #
    # API endpoints for employee portal (consumed by HRM)
    # ------------------------------------------------------------------ #

    @app.route("/healthz")
    def healthz():
        return jsonify({"ok": True, "system": SYSTEM_KEY})

    @app.route("/api/people/by-employee-number/<emp_number>")
    @api_auth_required("receipts", "view")
    def api_person_by_employee_number(emp_number):
        person = g.db.execute(
            "SELECT * FROM people WHERE employee_number = ? AND status = 'active'",
            (emp_number,),
        ).fetchone()
        if not person:
            return jsonify({"ok": False, "error": "not found"}), 404
        if not person_visible_to_current_access(person, "receipts", "view"):
            return jsonify({"ok": False, "error": "forbidden"}), 403
        return jsonify({"ok": True, "person": dict(person)})

    @app.route("/api/people/by-email/<email>")
    @api_auth_required("receipts", "view")
    def api_person_by_email(email):
        person = g.db.execute(
            "SELECT * FROM people WHERE email = ? AND status = 'active'",
            (email,),
        ).fetchone()
        if not person:
            return jsonify({"ok": False, "error": "not found"}), 404
        if not person_visible_to_current_access(person, "receipts", "view"):
            return jsonify({"ok": False, "error": "forbidden"}), 403
        return jsonify({"ok": True, "person": dict(person)})

    @app.route("/api/people/<int:person_id>/payments")
    @api_auth_required("payments", "view")
    def api_person_payments(person_id):
        _, error = require_api_person_access(person_id, "payments", "view")
        if error:
            return error
        payments = g.db.execute(
            """
            SELECT pp.id, pp.period_id, pp.gross_amount, pp.deductions_amount,
                   pp.net_amount, pp.status, pp.approved_at, pp.paid_at,
                   pp.created_at, pp.relationship_type,
                   p.name AS period_name, p.starts_on, p.ends_on,
                   pr.id AS receipt_id, pr.folio, pr.receipt_type,
                   pr.file_path, pr.status AS receipt_status
            FROM payroll_payments pp
            JOIN payroll_periods p ON p.id = pp.period_id
            LEFT JOIN payment_receipts pr ON pr.payment_id = pp.id
            WHERE pp.person_id = ?
            ORDER BY pp.created_at DESC
            """,
            (person_id,),
        ).fetchall()
        return jsonify({
            "ok": True,
            "payments": [dict(row) for row in payments],
        })

    @app.route("/api/people/<int:person_id>/receipts")
    @api_auth_required("receipts", "view")
    def api_person_receipts(person_id):
        _, error = require_api_person_access(person_id, "receipts", "view")
        if error:
            return error
        receipts = g.db.execute(
            """
            SELECT pr.id, pr.payment_id, pr.folio, pr.receipt_type,
                   pr.file_path, pr.status, pr.signed_at, pr.validated_at,
                   pr.created_at, pp.net_amount, pp.gross_amount,
                   p.name AS period_name, p.starts_on, p.ends_on
            FROM payment_receipts pr
            JOIN payroll_payments pp ON pp.id = pr.payment_id
            JOIN payroll_periods p ON p.id = pp.period_id
            WHERE pp.person_id = ?
            ORDER BY pr.created_at DESC
            """,
            (person_id,),
        ).fetchall()
        return jsonify({
            "ok": True,
            "receipts": [dict(row) for row in receipts],
        })

    @app.route("/api/receipts/<int:receipt_id>/download")
    @api_auth_required("receipts", "view")
    def api_receipt_download(receipt_id):
        receipt = g.db.execute(
            """
            SELECT pr.*, pp.person_id
            FROM payment_receipts pr
            JOIN payroll_payments pp ON pp.id = pr.payment_id
            WHERE pr.id = ?
            """,
            (receipt_id,),
        ).fetchone()
        if not receipt or not receipt["file_path"]:
            return jsonify({"ok": False, "error": "receipt or file not found"}), 404
        _, error = require_api_person_access(receipt["person_id"], "receipts", "view")
        if error:
            return error
        file_path = Path(receipt["file_path"])
        if not file_path.exists():
            return jsonify({"ok": False, "error": "file not found on disk"}), 404
        return send_from_directory(file_path.parent, file_path.name, as_attachment=True)

    @app.route("/api/people/<int:person_id>/contract")
    @api_auth_required("payments", "view")
    def api_person_contract(person_id):
        _, error = require_api_person_access(person_id, "payments", "view")
        if error:
            return error
        contract = g.db.execute(
            """
            SELECT * FROM contracts
            WHERE person_id = ? AND status = 'active'
            ORDER BY effective_from DESC LIMIT 1
            """,
            (person_id,),
        ).fetchone()
        if not contract:
            return jsonify({"ok": False, "error": "no active contract"}), 404
        return jsonify({"ok": True, "contract": dict(contract)})

    # ------------------------------------------------------------------ #
    # Web routes
    # ------------------------------------------------------------------ #

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
        audit_hq("login", "session", context["user"]["id"], "Ingreso a Payroll")
        return redirect(url_for("dashboard"))

    @app.route("/dashboard")
    @require_permission("reports", "view")
    def dashboard():
        stats = {
            "people": scalar("SELECT COUNT(*) FROM people"),
            "laboral": scalar("SELECT COUNT(*) FROM people WHERE contract_type = 'laboral'"),
            "mercantil": scalar("SELECT COUNT(*) FROM people WHERE contract_type = 'mercantil'"),
            "sales": scalar("SELECT COUNT(*) FROM sales_appointments"),
            "net_sales": scalar("SELECT COALESCE(SUM(net_sales), 0) FROM sales_appointments"),
            "unmatched_sales": scalar("SELECT COUNT(*) FROM sales_appointments WHERE person_id IS NULL"),
            "periods": scalar("SELECT COUNT(*) FROM payroll_periods"),
            "payments": scalar("SELECT COUNT(*) FROM payroll_payments"),
            "total_paid": scalar("SELECT COALESCE(SUM(net_amount), 0) FROM payroll_payments WHERE status IN ('approved', 'paid')"),
            "payments_draft": scalar("SELECT COUNT(*) FROM payroll_payments WHERE status = 'draft'"),
            "payments_paid": scalar("SELECT COUNT(*) FROM payroll_payments WHERE status = 'paid'"),
        }
        current_period = g.db.execute(
            """
            SELECT p.*,
                COALESCE(SUM(pay.net_amount), 0) AS total_payout,
                COUNT(pay.id) AS people_paid
            FROM payroll_periods p
            LEFT JOIN payroll_payments pay ON pay.period_id = p.id AND pay.status IN ('approved', 'paid')
            GROUP BY p.id
            ORDER BY p.starts_on DESC
            LIMIT 1
            """
        ).fetchone()
        periods_summary = g.db.execute(
            """
            SELECT p.id, p.name, p.starts_on, p.ends_on, p.status,
                COALESCE(SUM(pay.net_amount), 0) AS total_payout,
                COUNT(pay.id) AS people_count,
                SUM(CASE WHEN pay.status = 'draft' THEN 1 ELSE 0 END) AS drafts,
                SUM(CASE WHEN pay.status IN ('approved','paid') THEN 1 ELSE 0 END) AS finalized
            FROM payroll_periods p
            LEFT JOIN payroll_payments pay ON pay.period_id = p.id
            GROUP BY p.id
            ORDER BY p.starts_on DESC
            LIMIT 12
            """
        ).fetchall()
        top_staff = g.db.execute(
            """
            SELECT staff_name, center_name, COUNT(*) AS services, COALESCE(SUM(net_sales), 0) AS net_sales
            FROM sales_appointments
            GROUP BY staff_normalized_name, center_name
            ORDER BY net_sales DESC
            LIMIT 10
            """
        ).fetchall()
        recent_batches = g.db.execute("SELECT * FROM import_batches ORDER BY created_at DESC LIMIT 8").fetchall()
        trend_labels, trend_values = [], []
        for row in reversed(list(periods_summary)):
            trend_labels.append(row["name"])
            trend_values.append(row["total_payout"])
        return render_template(
            "dashboard.html",
            stats=stats,
            current_period=current_period,
            periods_summary=periods_summary,
            top_staff=top_staff,
            recent_batches=recent_batches,
            trend_labels=json.dumps(trend_labels, ensure_ascii=False),
            trend_values=json.dumps(trend_values),
        )

    @app.route("/people")
    @require_permission("people", "view")
    def people():
        PER_PAGE = 50
        page = int(request.args.get("page", 1))
        if page < 1: page = 1
        search = request.args.get("search", "").strip()
        relationship = request.args.get("relationship", "")
        where = []
        params = []
        scope_clause, scope_params = scoped_people_clause("people", "view")
        if scope_clause:
            where.append(scope_clause)
            params.extend(scope_params)
        if search:
            where.append("(full_name LIKE ? OR email LIKE ?)")
            params.extend([f"%{search}%", f"%{search}%"])
        if relationship:
            where.append("contract_type = ?")
            params.append(relationship)
        base_sql = "FROM people"
        if where:
            base_sql += " WHERE " + " AND ".join(where)
        total = scalar(f"SELECT COUNT(*) {base_sql}", params)
        total_pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)
        if page > total_pages: page = total_pages
        offset = (page - 1) * PER_PAGE
        query = f"SELECT * {base_sql} ORDER BY full_name LIMIT ? OFFSET ?"
        rows = g.db.execute(query, params + [PER_PAGE, offset]).fetchall()
        return render_template("people.html", rows=rows, search=search, relationship=relationship, page=page, total_pages=total_pages, total=total, per_page=PER_PAGE)

    @app.route("/people/<int:person_id>")
    @require_permission("people", "view")
    def person_detail(person_id):
        person = g.db.execute("SELECT * FROM people WHERE id = ?", (person_id,)).fetchone()
        if not person:
            flash("Persona no encontrada.", "danger")
            return redirect(url_for("people"))
        require_visible_person(person, "people", "view")
        contract = g.db.execute(
            "SELECT * FROM contracts WHERE person_id = ? AND status = 'active' ORDER BY effective_from DESC LIMIT 1",
            (person_id,),
        ).fetchone()
        contracts_all = g.db.execute(
            "SELECT * FROM contracts WHERE person_id = ? ORDER BY effective_from DESC",
            (person_id,),
        ).fetchall()
        payments = g.db.execute(
            """
            SELECT pp.*, p.name AS period_name, p.starts_on, p.ends_on
            FROM payroll_payments pp
            JOIN payroll_periods p ON p.id = pp.period_id
            WHERE pp.person_id = ?
            ORDER BY pp.created_at DESC LIMIT 10
            """,
            (person_id,),
        ).fetchall()
        return render_template("person_detail.html", person=person, contract=contract, contracts_all=contracts_all, payments=payments)

    @app.route("/people/<int:person_id>/payments")
    @require_permission("payments", "view")
    def person_payments(person_id):
        person = g.db.execute("SELECT * FROM people WHERE id = ?", (person_id,)).fetchone()
        if not person:
            flash("Persona no encontrada.", "danger")
            return redirect(url_for("people"))
        require_visible_person(person, "payments", "view")
        PER_PAGE = 50
        page = int(request.args.get("page", 1))
        if page < 1: page = 1
        total = scalar("SELECT COUNT(*) FROM payroll_payments WHERE person_id = ?", (person_id,))
        total_pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)
        if page > total_pages: page = total_pages
        offset = (page - 1) * PER_PAGE
        payments = g.db.execute(
            """
            SELECT pp.*, p.name AS period_name, p.starts_on, p.ends_on
            FROM payroll_payments pp
            JOIN payroll_periods p ON p.id = pp.period_id
            WHERE pp.person_id = ?
            ORDER BY pp.created_at DESC
            LIMIT ? OFFSET ?
            """,
            (person_id, PER_PAGE, offset),
        ).fetchall()
        summary = g.db.execute(
            """
            SELECT COUNT(*) AS total_payments,
                   COALESCE(SUM(CASE WHEN pp.status IN ('approved','paid') THEN pp.net_amount ELSE 0 END), 0) AS total_paid,
                   COALESCE(SUM(pp.gross_amount), 0) AS total_gross,
                   COALESCE(AVG(CASE WHEN pp.status IN ('approved','paid') THEN pp.net_amount ELSE NULL END), 0) AS avg_payment
            FROM payroll_payments pp
            WHERE pp.person_id = ?
            """,
            (person_id,),
        ).fetchone()
        return render_template("person_payments.html", person=person, payments=payments, summary=summary, page=page, total_pages=total_pages, total=total, per_page=PER_PAGE)

    @app.route("/people/<int:person_id>/payments.csv")
    @require_permission("payments", "view")
    def person_payments_csv(person_id):
        import csv as csv_module
        import io
        person = g.db.execute("SELECT * FROM people WHERE id = ?", (person_id,)).fetchone()
        if not person:
            flash("Persona no encontrada.", "danger")
            return redirect(url_for("people"))
        require_visible_person(person, "payments", "view")
        rows = g.db.execute(
            """
            SELECT pp.*, p.name AS period_name, p.starts_on, p.ends_on
            FROM payroll_payments pp
            JOIN payroll_periods p ON p.id = pp.period_id
            WHERE pp.person_id = ?
            ORDER BY pp.created_at DESC
            """,
            (person_id,),
        ).fetchall()
        output = io.StringIO()
        writer = csv_module.writer(output)
        writer.writerow(["Periodo", "Inicio", "Fin", "Bruto", "Deducciones", "Neto", "Estatus", "Aprobado", "Pagado"])
        for r in rows:
            writer.writerow([
                r["period_name"], r["starts_on"], r["ends_on"],
                r["gross_amount"], r["deductions_amount"], r["net_amount"],
                r["status"], r["approved_at"] or "", r["paid_at"] or "",
            ])
        csv_content = output.getvalue()
        output.close()
        from flask import Response as FlaskResponse
        return FlaskResponse(
            csv_content,
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment; filename=pagos_{person['normalized_name'].replace(' ', '_')}.csv"},
        )

    @app.route("/people/new", methods=["POST"])
    @require_permission("people", "create")
    def create_person():
        now = datetime.utcnow().isoformat()
        name = request.form["full_name"].strip()
        normalized = " ".join(name.lower().split())
        contract_type = request.form.get("contract_type", "mercantil")
        g.db.execute(
            """
            INSERT INTO people
            (full_name, normalized_name, email, phone, branch_name, relationship_type, contract_type, start_date, payment_day, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)
            """,
            (
                name,
                normalized,
                request.form.get("email", "").strip(),
                request.form.get("phone", "").strip(),
                request.form.get("branch_name", "").strip(),
                contract_type,
                contract_type,
                request.form.get("start_date", ""),
                request.form.get("payment_day", ""),
                now,
                now,
            ),
        )
        g.db.commit()
        audit_hq("create", "person", name, "Socia creada en Payroll")
        flash("Socia creada.", "success")
        return redirect(url_for("people"))

    @app.route("/sales")
    @require_permission("sales", "view")
    def sales():
        staff = request.args.get("staff", "")
        branch = request.args.get("branch", "")
        PER_PAGE = 100
        page = int(request.args.get("page", 1))
        if page < 1: page = 1
        params = []
        where = []
        scope = permission_scope("sales", "view")
        user = (g.hq_context or {}).get("user", {})
        if scope == "branch" and user.get("branch"):
            where.append("(sales_appointments.center_name = ? OR sales_appointments.branch_code = ?)")
            params.extend([user["branch"], user["branch"]])
        elif scope == "own" and user.get("email"):
            where.append("LOWER(people.email) = LOWER(?)")
            params.append(user["email"])
        elif scope not in {"all", "branch", "own"}:
            where.append("1 = 0")
        if staff:
            where.append("sales_appointments.staff_normalized_name LIKE ?")
            params.append(f"%{staff.lower()}%")
        if branch:
            where.append("sales_appointments.branch_code = ?")
            params.append(branch)
        base_sql = "FROM sales_appointments LEFT JOIN people ON people.id = sales_appointments.person_id"
        if where:
            base_sql += " WHERE " + " AND ".join(where)
        total = scalar(f"SELECT COUNT(*) {base_sql}", params)
        total_pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)
        if page > total_pages: page = total_pages
        offset = (page - 1) * PER_PAGE
        query = f"SELECT sales_appointments.* {base_sql} ORDER BY scheduled_at DESC LIMIT ? OFFSET ?"
        rows = g.db.execute(query, params + [PER_PAGE, offset]).fetchall()
        return render_template("sales.html", rows=rows, staff=staff, branch=branch,
                               page=page, total_pages=total_pages, total=total, per_page=PER_PAGE)

    @app.route("/periods", methods=["GET", "POST"])
    @require_permission("periods", "view")
    def periods():
        if request.method == "POST":
            if not has_permission("periods", "create"):
                flash("No tienes permiso para crear periodos.", "warning")
                return redirect(url_for("periods"))

            starts_on = request.form["starts_on"]
            ends_on = request.form["ends_on"]
            frequency = request.form.get("frequency", "weekly")

            # Validate dates
            if starts_on >= ends_on:
                flash("La fecha de inicio debe ser anterior a la fecha de fin.", "danger")
                return redirect(url_for("periods"))

            # Check for overlapping periods
            overlap = g.db.execute(
                """
                SELECT id, name FROM payroll_periods
                WHERE starts_on <= ? AND ends_on >= ?
                LIMIT 1
                """,
                (ends_on, starts_on),
            ).fetchone()
            if overlap:
                flash(f"El periodo se traslapa con \"{overlap['name']}\". Ajusta las fechas.", "danger")
                return redirect(url_for("periods"))

            now = datetime.utcnow().isoformat()
            g.db.execute(
                """
                INSERT INTO payroll_periods (name, frequency, starts_on, ends_on, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, 'draft', ?, ?)
                """,
                (
                    request.form["name"],
                    frequency,
                    starts_on,
                    ends_on,
                    now,
                    now,
                ),
            )
            g.db.commit()
            audit_hq("create", "period", request.form["name"], "Periodo creado en Payroll")
            flash("Periodo creado.", "success")
            return redirect(url_for("periods"))

        rows = g.db.execute("SELECT * FROM payroll_periods ORDER BY starts_on DESC").fetchall()

        # Add payment counts per period
        period_ids = [r["id"] for r in rows]
        payment_counts = {}
        if period_ids:
            placeholders = ",".join("?" for _ in period_ids)
            for row in g.db.execute(
                f"SELECT period_id, COUNT(*) AS c FROM payroll_payments WHERE period_id IN ({placeholders}) GROUP BY period_id",
                period_ids,
            ).fetchall():
                payment_counts[row["period_id"]] = row["c"]

        # Suggest next period dates based on last period
        last_row = g.db.execute(
            "SELECT ends_on, frequency FROM payroll_periods ORDER BY ends_on DESC LIMIT 1"
        ).fetchone()
        suggested = {}
        if last_row:
            next_start = datetime.fromisoformat(last_row["ends_on"]) + timedelta(days=1)
            freq_days = {"weekly": 7, "biweekly": 14, "monthly": 30}
            days = freq_days.get(last_row["frequency"], 7)
            suggested["starts_on"] = next_start.strftime("%Y-%m-%d")
            suggested["ends_on"] = (next_start + timedelta(days=days - 1)).strftime("%Y-%m-%d")
        else:
            suggested["starts_on"] = date.today().isoformat()
            suggested["ends_on"] = (date.today() + timedelta(days=6)).isoformat()

        return render_template("periods.html", rows=rows, today=date.today().isoformat(), suggested=suggested, payment_counts=payment_counts)

    @app.route("/periods/<int:period_id>/generate", methods=["POST"])
    @require_permission("payments", "create")
    def generate_payments(period_id):
        period = g.db.execute("SELECT * FROM payroll_periods WHERE id = ?", (period_id,)).fetchone()
        if not period:
            flash("Periodo no encontrado.", "danger")
            return redirect(url_for("periods"))
        people = g.db.execute("SELECT * FROM people WHERE status = 'active'").fetchall()
        now = datetime.utcnow().isoformat()
        created = 0
        for person in people:
            sales_total = g.db.execute(
                """
                SELECT COALESCE(SUM(net_sales), 0) AS total
                FROM sales_appointments
                WHERE person_id = ? AND DATE(scheduled_at) BETWEEN DATE(?) AND DATE(?)
                """,
                (person["id"], period["starts_on"], period["ends_on"]),
            ).fetchone()["total"]
            contract = g.db.execute(
                "SELECT * FROM contracts WHERE person_id = ? AND status = 'active' ORDER BY effective_from DESC LIMIT 1",
                (person["id"],),
            ).fetchone()
            gross, deductions, net, earnings_lines, deduction_lines, meta = calculate_payment(person, contract, sales_total)
            snapshot = json.dumps(dict(person), ensure_ascii=False)
            try:
                cursor = g.db.execute(
                    """
                    INSERT INTO payroll_payments
                    (period_id, person_id, person_snapshot, relationship_type, gross_amount, deductions_amount, net_amount, bono_punt_eligible, bono_ext_eligible, status, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 1, 1, 'draft', ?, ?)
                    """,
                    (period_id, person["id"], snapshot, person["contract_type"], gross, deductions, net, now, now),
                )
                payment_id = cursor.lastrowid
                for code, description, amount in earnings_lines:
                    g.db.execute(
                        """
                        INSERT INTO payment_lines
                        (payment_id, concept_code, description, amount, source_type, source_id, created_at)
                        VALUES (?, ?, ?, ?, 'calculation', ?, ?)
                        """,
                        (payment_id, code, description, amount, period_id, now),
                    )
                for code, description, amount in deduction_lines:
                    g.db.execute(
                        """
                        INSERT INTO payment_lines
                        (payment_id, concept_code, description, amount, source_type, source_id, created_at)
                        VALUES (?, ?, ?, ?, 'deduction', ?, ?)
                        """,
                        (payment_id, code, description, -amount, period_id, now),
                    )
                created += 1
            except Exception:
                pass
        g.db.commit()
        audit_hq("create", "payments", period_id, f"Pagos preliminares generados: {created}")
        flash(f"Pagos preliminares generados: {created}.", "success")
        return redirect(url_for("payments", period_id=period_id))

    @app.route("/payments")
    @require_permission("payments", "view")
    def payments():
        period_id = request.args.get("period_id", "")
        status_filter = request.args.get("status", "").strip()
        search = request.args.get("search", "").strip()
        PER_PAGE = 100
        page = int(request.args.get("page", 1))
        if page < 1: page = 1
        where = []
        params = []
        scope_clause, scope_params = scoped_people_clause("payments", "view")
        if scope_clause:
            where.append(scope_clause)
            params.extend(scope_params)
        if period_id:
            where.append("payroll_payments.period_id = ?")
            params.append(period_id)
        if status_filter:
            where.append("payroll_payments.status = ?")
            params.append(status_filter)
        if search:
            where.append("people.full_name LIKE ?")
            params.append(f"%{search}%")
        base_sql = """
            FROM payroll_payments
            JOIN people ON people.id = payroll_payments.person_id
            JOIN payroll_periods ON payroll_periods.id = payroll_payments.period_id
        """
        if where:
            base_sql += " WHERE " + " AND ".join(where)
        total = scalar(f"SELECT COUNT(*) {base_sql}", params)
        total_pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)
        if page > total_pages: page = total_pages
        offset = (page - 1) * PER_PAGE
        query = f"""
            SELECT payroll_payments.*, people.full_name, people.branch_name,
                   people.relationship_type, payroll_periods.name AS period_name
            {base_sql}
            ORDER BY payroll_payments.created_at DESC
            LIMIT ? OFFSET ?
        """
        rows = g.db.execute(query, params + [PER_PAGE, offset]).fetchall()
        periods = g.db.execute("SELECT * FROM payroll_periods ORDER BY starts_on DESC").fetchall()
        return render_template("payments.html", rows=rows, periods=periods, period_id=period_id,
                               status_filter=status_filter, search=search, page=page,
                               total_pages=total_pages, total=total, per_page=PER_PAGE)

    @app.route("/imports")
    @require_permission("reports", "view")
    def imports():
        search = request.args.get("search", "").strip()
        import_type = request.args.get("import_type", "").strip()
        PER_PAGE = 50
        page = int(request.args.get("page", 1))
        if page < 1: page = 1

        # Use import_batches table for paginated display
        where = []
        params = []
        if search:
            where.append("file_name LIKE ?")
            params.append(f"%{search}%")
        if import_type:
            where.append("source = ?")
            params.append(import_type)
        base_sql = "FROM import_batches"
        if where:
            base_sql += " WHERE " + " AND ".join(where)
        total = scalar(f"SELECT COUNT(*) {base_sql}", params)
        total_pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)
        if page > total_pages: page = total_pages
        offset = (page - 1) * PER_PAGE
        rows = g.db.execute(
            f"SELECT * {base_sql} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params + [PER_PAGE, offset]
        ).fetchall()

        # Stats for the header
        stats = {
            "payroll_rows": scalar("SELECT COUNT(*) FROM payroll_run_imports"),
            "payroll_matched": scalar("SELECT COUNT(*) FROM payroll_run_imports WHERE matched_person_id IS NOT NULL"),
            "contract_rows": scalar("SELECT COUNT(*) FROM contract_roster_imports"),
            "contract_matched": scalar("SELECT COUNT(*) FROM contract_roster_imports WHERE matched_person_id IS NOT NULL"),
            "baja_rows": scalar("SELECT COUNT(*) FROM contract_roster_imports WHERE lower(status) = 'baja' OR end_date != '' OR baja_reason != ''"),
            "total_batches": total,
        }
        return render_template("imports.html", rows=rows, stats=stats,
                               search=search, import_type=import_type,
                               page=page, total_pages=total_pages, total=total, per_page=PER_PAGE)

    @app.route("/imports/<int:batch_id>")
    @require_permission("reports", "view")
    def import_detail(batch_id):
        batch = g.db.execute("SELECT * FROM import_batches WHERE id = ?", (batch_id,)).fetchone()
        if not batch:
            flash("Importacion no encontrada.", "danger")
            return redirect(url_for("imports"))

        payroll_rows = g.db.execute(
            """
            SELECT pri.*, p.full_name AS matched_name
            FROM payroll_run_imports pri
            LEFT JOIN people p ON p.id = pri.matched_person_id
            WHERE pri.import_batch_id = ?
            ORDER BY pri.source_scheme, pri.row_number
            LIMIT 500
            """,
            (batch_id,),
        ).fetchall()
        roster_rows = g.db.execute(
            """
            SELECT cri.*, p.full_name AS matched_name
            FROM contract_roster_imports cri
            LEFT JOIN people p ON p.id = cri.matched_person_id
            WHERE cri.import_batch_id = ?
            ORDER BY cri.row_number
            LIMIT 500
            """,
            (batch_id,),
        ).fetchall()
        return render_template("import_detail.html", batch=batch, payroll_rows=payroll_rows, roster_rows=roster_rows)

    @app.route("/payments/<int:payment_id>/recalculate", methods=["POST"])
    @require_permission("payments", "edit")
    def recalculate_payment(payment_id):
        require_visible_payment(payment_id, "payments", "edit")
        now = datetime.utcnow().isoformat()
        try:
            _recalculate_payment(payment_id, now)
            g.db.commit()
            audit_hq("recalculate", "payment", payment_id, "Pago recalculado")
            flash("Pago recalculado.", "success")
        except ValueError as e:
            flash(str(e), "danger")
        except Exception:
            flash("Error al recalcular pago.", "danger")
        return redirect(url_for("payments"))

    @app.route("/payments/<int:payment_id>/edit", methods=["GET", "POST"])
    @require_permission("payments", "edit")
    def edit_payment(payment_id):
        payment = g.db.execute(
            """
            SELECT pp.*, people.full_name, people.branch_name, people.normalized_name,
                   payroll_periods.name AS period_name, payroll_periods.starts_on, payroll_periods.ends_on
            FROM payroll_payments pp
            JOIN people ON people.id = pp.person_id
            JOIN payroll_periods ON payroll_periods.id = pp.period_id
            WHERE pp.id = ?
            """,
            (payment_id,),
        ).fetchone()
        if not payment:
            flash("Pago no encontrado.", "danger")
            return redirect(url_for("payments"))
        payment_person = g.db.execute("SELECT * FROM people WHERE id = ?", (payment["person_id"],)).fetchone()
        require_visible_person(payment_person, "payments", "edit")

        if request.method == "POST":
            target_status = request.form.get("status", payment["status"])
            if target_status == "approved" and not has_permission("payments", "approve"):
                flash("No tienes permiso para aprobar pagos.", "warning")
                return redirect(url_for("edit_payment", payment_id=payment_id))

            now = datetime.utcnow().isoformat()
            gross = float(request.form.get("gross_amount", payment["gross_amount"]) or 0)
            deductions = float(request.form.get("deductions_amount", payment["deductions_amount"]) or 0)
            net = float(request.form.get("net_amount", payment["net_amount"]) or 0)
            if not request.form.get("net_amount"):
                net = gross - deductions

            g.db.execute(
                """
                UPDATE payroll_payments
                SET gross_amount = ?, deductions_amount = ?, net_amount = ?,
                    status = ?, bono_punt_eligible = ?, bono_ext_eligible = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    gross,
                    deductions,
                    net,
                    target_status,
                    1 if request.form.get("bono_punt_eligible") else 0,
                    1 if request.form.get("bono_ext_eligible") else 0,
                    now,
                    payment_id,
                ),
            )
            g.db.execute(
                "INSERT INTO payment_history (payment_id, action, actor, detail, created_at) VALUES (?, 'manual_edit', ?, ?, ?)",
                (payment_id, current_actor_name(), f"Pago editado manualmente. Neto: {net}", now),
            )
            g.db.commit()
            audit_hq("manual_edit", "payment", payment_id, "Pago editado manualmente")
            flash("Pago actualizado.", "success")
            return redirect(url_for("edit_payment", payment_id=payment_id))

        lines = g.db.execute(
            "SELECT * FROM payment_lines WHERE payment_id = ? ORDER BY source_type, id",
            (payment_id,),
        ).fetchall()
        history = g.db.execute(
            "SELECT * FROM payment_history WHERE payment_id = ? ORDER BY created_at DESC LIMIT 20",
            (payment_id,),
        ).fetchall()
        payroll_imports = g.db.execute(
            """
            SELECT * FROM payroll_run_imports
            WHERE matched_person_id = ?
            ORDER BY created_at DESC, source_scheme, row_number
            LIMIT 25
            """,
            (payment["person_id"],),
        ).fetchall()
        sales_rows = g.db.execute(
            """
            SELECT ref_cita, client_name, service, scheduled_at, center_name, net_sales, status
            FROM sales_appointments
            WHERE person_id = ? AND DATE(scheduled_at) BETWEEN DATE(?) AND DATE(?)
            ORDER BY scheduled_at DESC
            LIMIT 50
            """,
            (payment["person_id"], payment["starts_on"], payment["ends_on"]),
        ).fetchall()
        return render_template(
            "payment_edit.html",
            payment=payment,
            lines=lines,
            history=history,
            payroll_imports=payroll_imports,
            sales_rows=sales_rows,
        )

    @app.route("/payments/<int:payment_id>/status", methods=["POST"])
    @require_permission("payments", "edit")
    def update_payment_status(payment_id):
        require_visible_payment(payment_id, "payments", "edit")
        if request.form["status"] == "approved" and not has_permission("payments", "approve"):
            flash("No tienes permiso para aprobar pagos.", "warning")
            return redirect(url_for("payments"))
        status = request.form["status"]
        now = datetime.utcnow().isoformat()
        _apply_payment_status(payment_id, status, now)
        g.db.commit()
        audit_hq(status, "payment", payment_id, f"Pago marcado como {status}")
        flash("Pago actualizado.", "success")
        return redirect(url_for("payments"))

    @app.route("/payments/batch-status", methods=["POST"])
    @require_permission("payments", "edit")
    def batch_payment_status():
        target_status = request.form.get("target_status", "")
        payment_ids = request.form.getlist("payment_ids")

        if target_status not in ("approved", "rejected", "paid", "draft"):
            flash("Estatus invalido.", "danger")
            return redirect(url_for("payments"))
        if target_status == "approved" and not has_permission("payments", "approve"):
            flash("No tienes permiso para aprobar pagos.", "warning")
            return redirect(url_for("payments"))
        if not payment_ids:
            flash("Selecciona al menos un pago.", "warning")
            return redirect(url_for("payments"))

        now = datetime.utcnow().isoformat()
        count = 0
        for pid in payment_ids:
            try:
                require_visible_payment(int(pid), "payments", "edit")
                _apply_payment_status(int(pid), target_status, now)
                count += 1
            except Exception:
                pass
        g.db.commit()
        audit_hq("batch_status", "payment", ",".join(payment_ids), f"{count} pagos marcados como {target_status}")
        flash(f"{count} pagos actualizados a {target_status}.", "success")
        return redirect(url_for("payments"))

    @app.route("/payments/<int:payment_id>/advance", methods=["POST"])
    @require_permission("payments", "edit")
    def set_payment_advance(payment_id):
        require_visible_payment(payment_id, "payments", "edit")
        payment = g.db.execute("SELECT status FROM payroll_payments WHERE id = ?", (payment_id,)).fetchone()
        if not payment:
            flash("Pago no encontrado.", "danger")
            return redirect(url_for("payments"))
        if payment["status"] not in ("draft",):
            flash("Solo se pueden ajustar anticipos en pagos draft.", "warning")
            return redirect(url_for("payments"))

        amount = float(request.form.get("advance_amount", 0) or 0)
        now = datetime.utcnow().isoformat()

        # Remove existing advance line
        g.db.execute(
            "DELETE FROM payment_lines WHERE payment_id = ? AND source_type = 'advance'",
            (payment_id,),
        )
        if amount:
            g.db.execute(
                "INSERT INTO payment_lines (payment_id, concept_code, description, amount, source_type, source_id, created_at) VALUES (?, 'ADVANCE', 'Anticipo', ?, 'advance', ?, ?)",
                (payment_id, -abs(amount), f"manual:{now}", now),
            )
        g.db.commit()
        flash(f"Anticipo de ${amount:,.2f} registrado." if amount else "Anticipo eliminado.", "success")
        return redirect(url_for("payments"))

    @app.route("/periods/<int:period_id>/recalculate", methods=["POST"])
    @require_permission("payments", "edit")
    def recalculate_period_payments(period_id):
        scope_clause, scope_params = scoped_people_clause("payments", "edit")
        scope_sql = f" AND {scope_clause}" if scope_clause else ""
        draft_ids = [
            r["id"] for r in g.db.execute(
                f"""
                SELECT payroll_payments.id
                FROM payroll_payments
                JOIN people ON people.id = payroll_payments.person_id
                WHERE payroll_payments.period_id = ? AND payroll_payments.status = 'draft'{scope_sql}
                """,
                [period_id] + scope_params,
            ).fetchall()
        ]
        if not draft_ids:
            flash("No hay pagos draft en este periodo.", "warning")
            return redirect(url_for("payments", period_id=period_id))

        now = datetime.utcnow().isoformat()
        ok = 0
        errors = 0
        for pid in draft_ids:
            try:
                _recalculate_payment(pid, now)
                ok += 1
            except Exception:
                errors += 1
        g.db.commit()
        audit_hq("recalculate_batch", "period", period_id, f"{ok} pagos recalculados, {errors} errores")
        flash(f"{ok} pagos recalculados en el periodo.", "success" if ok else "danger")
        return redirect(url_for("payments", period_id=period_id))

    @app.route("/payments/export.csv")
    @require_permission("payments", "view")
    def export_payments_csv():
        import csv as csv_module
        import io

        period_id = request.args.get("period_id", "")
        params = []
        query = """
            SELECT payroll_payments.*, people.full_name, people.branch_name,
                   payroll_periods.name AS period_name, payroll_periods.starts_on,
                   payroll_periods.ends_on
            FROM payroll_payments
            JOIN people ON people.id = payroll_payments.person_id
            JOIN payroll_periods ON payroll_periods.id = payroll_payments.period_id
        """
        if period_id:
            query += " WHERE payroll_payments.period_id = ?"
            params.append(period_id)
        scope_clause, scope_params = scoped_people_clause("payments", "view")
        if scope_clause:
            query += (" AND " if period_id else " WHERE ") + scope_clause
            params.extend(scope_params)
        query += " ORDER BY people.branch_name, people.full_name"
        rows = g.db.execute(query, params).fetchall()

        output = io.StringIO()
        writer = csv_module.writer(output)
        writer.writerow(["Periodo", "Inicio", "Fin", "Socia", "Sucursal", "Tipo", "Bruto", "Deducciones", "Neto", "Estatus", "Aprobado", "Pagado"])
        for r in rows:
            writer.writerow([
                r["period_name"], r["starts_on"], r["ends_on"],
                r["full_name"], r["branch_name"], r["relationship_type"],
                r["gross_amount"], r["deductions_amount"], r["net_amount"],
                r["status"], r["approved_at"] or "", r["paid_at"] or "",
            ])
        csv_content = output.getvalue()
        output.close()

        from flask import Response as FlaskResponse
        return FlaskResponse(
            csv_content,
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment; filename=pagos_{date.today().isoformat()}.csv"},
        )

    def _ensure_receipt(payment_id):
        existing = g.db.execute("SELECT * FROM payment_receipts WHERE payment_id = ?", (payment_id,)).fetchone()
        if existing:
            return existing
        now = datetime.utcnow().isoformat()
        payment = g.db.execute("SELECT * FROM payroll_payments WHERE id = ?", (payment_id,)).fetchone()
        if not payment:
            return None
        year = date.today().year
        last = g.db.execute(
            "SELECT folio FROM payment_receipts WHERE folio LIKE ? ORDER BY id DESC LIMIT 1",
            (f"VPR-{year}-%",),
        ).fetchone()
        seq = 1
        if last:
            seq = int(last["folio"].rsplit("-", 1)[-1]) + 1
        folio = f"VPR-{year}-{seq:04d}"
        cursor = g.db.execute(
            "INSERT INTO payment_receipts (payment_id, folio, receipt_type, status, created_at) VALUES (?, ?, 'internal', 'draft', ?)",
            (payment_id, folio, now),
        )
        receipt_id = cursor.lastrowid
        return g.db.execute("SELECT * FROM payment_receipts WHERE id = ?", (receipt_id,)).fetchone()

    @app.route("/payments/<int:payment_id>/receipt")
    @require_permission("payments", "view")
    def payment_receipt_view(payment_id):
        payment = g.db.execute("SELECT * FROM payroll_payments WHERE id = ?", (payment_id,)).fetchone()
        if not payment:
            flash("Pago no encontrado.", "danger")
            return redirect(url_for("payments"))
        person = g.db.execute("SELECT * FROM people WHERE id = ?", (payment["person_id"],)).fetchone()
        require_visible_person(person, "payments", "view")
        period = g.db.execute("SELECT * FROM payroll_periods WHERE id = ?", (payment["period_id"],)).fetchone()
        lines = g.db.execute(
            "SELECT * FROM payment_lines WHERE payment_id = ? ORDER BY source_type, id",
            (payment_id,),
        ).fetchall()
        receipt = _ensure_receipt(payment_id)
        return render_template(
            "receipt.html",
            payment=payment,
            person=person,
            period=period,
            lines=lines,
            receipt=receipt,
        )

    @app.route("/payments/<int:payment_id>/receipt/pdf")
    @require_permission("payments", "view")
    def payment_receipt_pdf(payment_id):
        from weasyprint import HTML
        import tempfile
        payment = g.db.execute("SELECT * FROM payroll_payments WHERE id = ?", (payment_id,)).fetchone()
        if not payment:
            flash("Pago no encontrado.", "danger")
            return redirect(url_for("payments"))
        person = g.db.execute("SELECT * FROM people WHERE id = ?", (payment["person_id"],)).fetchone()
        require_visible_person(person, "payments", "view")
        period = g.db.execute("SELECT * FROM payroll_periods WHERE id = ?", (payment["period_id"],)).fetchone()
        lines = g.db.execute(
            "SELECT * FROM payment_lines WHERE payment_id = ? ORDER BY source_type, id",
            (payment_id,),
        ).fetchall()
        receipt = _ensure_receipt(payment_id)
        html_str = render_template(
            "receipt.html",
            payment=payment,
            person=person,
            period=period,
            lines=lines,
            receipt=receipt,
        )
        pdf_path = Path(tempfile.mkdtemp()) / f"recibo_{receipt['folio']}.pdf"
        HTML(string=html_str).write_pdf(str(pdf_path))
        g.db.execute("UPDATE payment_receipts SET file_path = ?, status = 'generated' WHERE id = ?", (str(pdf_path), receipt["id"]))
        g.db.commit()
        return send_from_directory(pdf_path.parent, pdf_path.name, as_attachment=True)

    # --- Batch receipt generation ---
    @app.route("/payments/batch-receipts", methods=["POST"])
    @require_permission("payments", "edit")
    def batch_receipts():
        payment_ids = request.form.getlist("payment_ids")
        if not payment_ids:
            flash("Selecciona al menos un pago.", "warning")
            return redirect(url_for("payments"))
        count = 0
        for pid in payment_ids:
            payment = g.db.execute("SELECT status FROM payroll_payments WHERE id = ?", (pid,)).fetchone()
            if payment and payment["status"] in ("approved", "paid"):
                _ensure_receipt(int(pid))
                count += 1
        g.db.commit()
        flash(f"{count} recibos generados.", "success")
        return redirect(url_for("payments"))

    # --- Bonus toggle per payment ---
    @app.route("/payments/<int:payment_id>/bonus", methods=["POST"])
    @require_permission("payments", "edit")
    def toggle_bonus(payment_id):
        require_visible_payment(payment_id, "payments", "edit")
        field = request.form.get("field", "")
        if field not in ("bono_punt_eligible", "bono_ext_eligible"):
            flash("Campo invalido.", "danger")
            return redirect(url_for("payments"))
        now = datetime.utcnow().isoformat()
        g.db.execute(
            f"UPDATE payroll_payments SET {field} = CASE WHEN {field} = 1 THEN 0 ELSE 1 END, updated_at = ? WHERE id = ?",
            (now, payment_id),
        )
        g.db.commit()
        flash("Bono actualizado.", "success")
        return redirect(url_for("payments"))

    # --- Edit person ---
    @app.route("/people/<int:person_id>/edit", methods=["GET", "POST"])
    @require_permission("people", "edit")
    def edit_person(person_id):
        person = g.db.execute("SELECT * FROM people WHERE id = ?", (person_id,)).fetchone()
        if not person:
            flash("Persona no encontrada.", "danger")
            return redirect(url_for("people"))
        require_visible_person(person, "people", "edit")
        if request.method == "POST":
            now = datetime.utcnow().isoformat()
            fields = ["full_name", "email", "phone", "branch_name", "relationship_type", "contract_type", "start_date", "end_date", "payment_day", "tax_id", "curp", "bank_name", "bank_account", "clabe"]
            updates = {k: request.form.get(k, "").strip() for k in fields}
            updates["normalized_name"] = " ".join(updates["full_name"].lower().split())
            sets = ", ".join(f"{k} = ?" for k in updates)
            values = list(updates.values()) + [now, person_id]
            g.db.execute(f"UPDATE people SET {sets}, updated_at = ? WHERE id = ?", values)
            g.db.commit()
            audit_hq("edit", "person", person_id, "Socia actualizada")
            flash("Socia actualizada.", "success")
            return redirect(url_for("person_detail", person_id=person_id))
        return render_template("person_edit.html", person=person)

    # --- Edit contract ---
    @app.route("/people/<int:person_id>/contract", methods=["GET", "POST"])
    @require_permission("people", "edit")
    def edit_contract(person_id):
        person = g.db.execute("SELECT * FROM people WHERE id = ?", (person_id,)).fetchone()
        if not person:
            flash("Persona no encontrada.", "danger")
            return redirect(url_for("people"))
        require_visible_person(person, "people", "edit")
        if request.method == "POST":
            now = datetime.utcnow().isoformat()
            contract_type = request.form.get("contract_type", person["contract_type"])
            base_salary = float(request.form.get("base_salary", 0) or 0)
            commission_rate = float(request.form.get("commission_rate", 0) or 0)
            rules = {}
            for key in request.form:
                if key.startswith("rule_"):
                    rules[key[5:]] = request.form[key]
            g.db.execute(
                "UPDATE contracts SET contract_type = ?, base_salary = ?, commission_rate = ?, rules_json = ?, updated_at = ? WHERE person_id = ? AND status = 'active'",
                (contract_type, base_salary, commission_rate, json.dumps(rules, ensure_ascii=False), now, person_id),
            )
            g.db.execute("UPDATE people SET contract_type = ?, updated_at = ? WHERE id = ?", (contract_type, now, person_id))
            g.db.commit()
            audit_hq("edit", "contract", person_id, "Contrato actualizado")
            flash("Contrato actualizado.", "success")
            return redirect(url_for("person_detail", person_id=person_id))
        contract = g.db.execute(
            "SELECT * FROM contracts WHERE person_id = ? AND status = 'active' ORDER BY effective_from DESC LIMIT 1",
            (person_id,),
        ).fetchone()
        return render_template("contract_edit.html", person=person, contract=contract)


def _apply_payment_status(payment_id, status, now):
    fields = ["status = ?", "updated_at = ?"]
    values = [status, now]
    actor = current_actor_name()
    if status == "approved":
        fields.extend(["approved_by = ?", "approved_at = ?"])
        values.extend([actor, now])
    if status == "paid":
        fields.append("paid_at = ?")
        values.append(now)
    values.append(payment_id)
    g.db.execute(f"UPDATE payroll_payments SET {', '.join(fields)} WHERE id = ?", values)
    g.db.execute(
        "INSERT INTO payment_history (payment_id, action, actor, detail, created_at) VALUES (?, ?, ?, ?, ?)",
        (payment_id, status, actor, f"Pago marcado como {status}", now),
    )


def _recalculate_payment(payment_id, now):
    payment = g.db.execute(
        "SELECT * FROM payroll_payments WHERE id = ?", (payment_id,)
    ).fetchone()
    if not payment:
        raise ValueError("payment not found")
    if payment["status"] not in ("draft",):
        raise ValueError("only draft payments can be recalculated")

    person = g.db.execute("SELECT * FROM people WHERE id = ?", (payment["person_id"],)).fetchone()
    if not person:
        raise ValueError("person not found")

    period = g.db.execute("SELECT * FROM payroll_periods WHERE id = ?", (payment["period_id"],)).fetchone()
    if not period:
        raise ValueError("period not found")

    sales_total = g.db.execute(
        """
        SELECT COALESCE(SUM(net_sales), 0) AS total
        FROM sales_appointments
        WHERE person_id = ? AND DATE(scheduled_at) BETWEEN DATE(?) AND DATE(?)
        """,
        (person["id"], period["starts_on"], period["ends_on"]),
    ).fetchone()["total"]

    contract = g.db.execute(
        "SELECT * FROM contracts WHERE person_id = ? AND status = 'active' ORDER BY effective_from DESC LIMIT 1",
        (person["id"],),
    ).fetchone()

    bono_punt = bool(payment["bono_punt_eligible"])
    bono_ext = bool(payment["bono_ext_eligible"])
    gross, _, net, earnings_lines, deduction_lines, meta = calculate_payment(person, contract, sales_total, bono_punt_eligible=bono_punt, bono_ext_eligible=bono_ext)

    advance_total = g.db.execute(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM payment_lines WHERE payment_id = ? AND source_type = 'advance'",
        (payment_id,),
    ).fetchone()["total"]

    deductions_total = 0.0
    if advance_total:
        deduction_lines.append(("ADVANCE", "Anticipo", advance_total))
        deductions_total = advance_total
        net -= advance_total

    snapshot = json.dumps({**dict(person), "_meta": meta}, ensure_ascii=False)
    g.db.execute(
        """
        UPDATE payroll_payments
        SET person_snapshot = ?, gross_amount = ?, deductions_amount = ?, net_amount = ?, updated_at = ?
        WHERE id = ?
        """,
        (snapshot, gross, deductions_total, net, now, payment_id),
    )

    g.db.execute("DELETE FROM payment_lines WHERE payment_id = ? AND source_type IN ('calculation', 'deduction')", (payment_id,))
    for code, description, amount in earnings_lines:
        g.db.execute(
            "INSERT INTO payment_lines (payment_id, concept_code, description, amount, source_type, source_id, created_at) VALUES (?, ?, ?, ?, 'calculation', ?, ?)",
            (payment_id, code, description, amount, period["id"], now),
        )
    for code, description, amount in deduction_lines:
        g.db.execute(
            "INSERT INTO payment_lines (payment_id, concept_code, description, amount, source_type, source_id, created_at) VALUES (?, ?, ?, ?, 'deduction', ?, ?)",
            (payment_id, code, description, -abs(amount), period["id"], now),
        )


def scalar(query, params=()):
    return g.db.execute(query, params).fetchone()[0]


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.getenv("PORT", "5051")), debug=True)
