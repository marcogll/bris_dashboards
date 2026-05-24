import csv
import json
import logging
import os
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from flask import (
    Flask,
    Response,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from werkzeug.security import check_password_hash, generate_password_hash

# ──────────────────────────────────────────────
#  Logging
# ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("bris_dashboard")

# ──────────────────────────────────────────────
#  Config
# ──────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = Path(os.getenv("DATA_FILE", BASE_DIR / "data" / "stations.csv"))
AVAILABLE_SECONDS = float(os.getenv("AVAILABLE_SECONDS", "39900"))
TAKT_SECONDS = float(os.getenv("TAKT_SECONDS", "2216.666667"))
APP_TITLE = os.getenv("APP_TITLE", "BRIS Rack Assembly Dashboard")
UPLOAD_SECRET = os.getenv("UPLOAD_SECRET", "")

CURATED_DIR = BASE_DIR / "adriana_projects" / "data" / "curated"
USERS_FILE = BASE_DIR / "data" / "users.json"
FALLBACKS_DIR = BASE_DIR / "data" / "fallbacks"

app = Flask(__name__)

SECRET_KEY = os.getenv("SECRET_KEY", "")
FLASK_ENV = os.getenv("FLASK_ENV", "production")
if not SECRET_KEY and FLASK_ENV != "development":
    raise RuntimeError(
        "SECRET_KEY debe estar definido en producción. "
        "Establece la variable de entorno SECRET_KEY."
    )
app.secret_key = SECRET_KEY or "local-dev-change-me"

# ──────────────────────────────────────────────
#  Security headers
# ──────────────────────────────────────────────
@app.after_request
def add_security_headers(response: Response) -> Response:
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers[
        "Content-Security-Policy"
    ] = (
        "default-src 'self'; "
        "style-src 'self' https://fonts.googleapis.com; "
        "font-src https://fonts.gstatic.com; "
        "img-src 'self' data:; "
        "script-src 'self' 'unsafe-inline'"
    )
    return response


# ──────────────────────────────────────────────
#  Authentication
# ──────────────────────────────────────────────
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Inicia sesión para acceder al dashboard."


class User(UserMixin):
    def __init__(self, uid: str, username: str, password_hash: str, role: str = "user"):
        super().__init__()
        self.id = uid
        self.username = username
        self.password_hash = password_hash
        self.role = role


def _load_users() -> dict:
    if USERS_FILE.exists():
        return json.loads(USERS_FILE.read_text(encoding="utf-8"))
    return {}


def _save_users(data: dict) -> None:
    USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    USERS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _ensure_default_user() -> None:
    users = _load_users()
    if "marco" not in users:
        admin_password = os.getenv("ADMIN_DEFAULT_PASSWORD", "")
        if not admin_password:
            import secrets

            admin_password = secrets.token_urlsafe(16)
            logger.warning(
                "ADMIN_DEFAULT_PASSWORD no está definido. "
                f"Se generó una contraseña temporal para 'marco': {admin_password}"
            )
        users["marco"] = {
            "id": "1",
            "username": "marco",
            "password_hash": generate_password_hash(admin_password),
            "role": "admin",
        }
        _save_users(users)


_ensure_default_user()


@login_manager.user_loader
def load_user(user_id: str):
    users = _load_users()
    for u in users.values():
        if u.get("id") == user_id:
            return User(u["id"], u["username"], u["password_hash"], u.get("role", "user"))
    return None


# ──────────────────────────────────────────────
#  Data models
# ──────────────────────────────────────────────
@dataclass
class Station:
    station_id: str
    station_name: str
    time_seconds: float
    operators: float
    observations: str
    action: str

    @property
    def capacity_per_hour(self) -> float:
        if self.time_seconds <= 0:
            return 0
        return self.operators * 3600 / self.time_seconds

    @property
    def work_minutes(self) -> float:
        return self.time_seconds / 60

    @property
    def effective_cycle_seconds(self) -> float:
        if self.operators <= 0:
            return self.time_seconds
        return self.time_seconds / self.operators


# ──────────────────────────────────────────────
#  CSV helpers with simple mtime cache
# ──────────────────────────────────────────────
_csv_cache: dict[Path, tuple[float, list[dict]]] = {}


def as_float(value: str, default: float = 0) -> float:
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return default


def read_csv_safe(path: Path) -> list[dict]:
    """Read a curated CSV; return empty list if missing."""
    if not path.exists():
        return []
    mtime = path.stat().st_mtime
    cached = _csv_cache.get(path)
    if cached and cached[0] == mtime:
        return cached[1]
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    _csv_cache[path] = (mtime, rows)
    return rows


def invalidate_csv_cache(path: Path | None = None) -> None:
    """Clear CSV cache. If path is None, clear all."""
    global _csv_cache
    if path is None:
        _csv_cache = {}
    else:
        _csv_cache.pop(path, None)


def read_stations() -> list[Station]:
    if not DATA_FILE.exists():
        return []
    with DATA_FILE.open(newline="", encoding="utf-8-sig") as file:
        rows = csv.DictReader(file)
        stations: list[Station] = []
        for row in rows:
            station_name = (row.get("station_name") or row.get("station") or "").strip()
            if not station_name:
                continue
            stations.append(
                Station(
                    station_id=(row.get("station_id") or str(len(stations) + 1)).strip(),
                    station_name=station_name,
                    time_seconds=as_float(row.get("time_seconds")),
                    operators=as_float(row.get("operators"), 1),
                    observations=(row.get("observations") or "").strip(),
                    action=(row.get("action") or "").strip(),
                )
            )
    return stations


def _load_fallback(filename: str) -> list[dict] | dict:
    p = FALLBACKS_DIR / filename
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    logger.warning("Fallback no encontrado: %s", p)
    return []


# ──────────────────────────────────────────────
#  Metrics engine
# ──────────────────────────────────────────────
def build_metrics(stations: list[Station]) -> dict[str, Any]:
    if not stations:
        return {
            "stations": [],
            "bottleneck": None,
            "total_work_seconds": 0,
            "target_units": AVAILABLE_SECONDS / TAKT_SECONDS,
            "actual_units": 0,
            "gap_units": 0,
            "scenario": None,
            "max_capacity": 0,
            "takt_utilization": 0,
        }

    total_work_seconds = sum(s.time_seconds for s in stations)
    target_units = AVAILABLE_SECONDS / TAKT_SECONDS if TAKT_SECONDS else 0
    bottleneck = min(stations, key=lambda s: s.capacity_per_hour)
    actual_units = bottleneck.capacity_per_hour * AVAILABLE_SECONDS / 3600
    gap_units = target_units - actual_units
    max_capacity = max(s.capacity_per_hour for s in stations)

    enriched = []
    for station in stations:
        work_share = station.time_seconds / total_work_seconds * 100 if total_work_seconds else 0
        takt_gap = station.time_seconds - TAKT_SECONDS
        is_over_takt = takt_gap > 0
        status = "critical" if station == bottleneck else "warning" if is_over_takt else "ok"
        takt_pct = station.time_seconds / TAKT_SECONDS * 100 if TAKT_SECONDS else 0
        enriched.append(
            {
                "raw": station,
                "work_share": work_share,
                "takt_gap": takt_gap,
                "takt_pct": takt_pct,
                "status": status,
                "bar_width": station.capacity_per_hour / max_capacity * 100 if max_capacity else 0,
            }
        )

    scenario = best_one_operator_rebalance(stations)
    takt_utilization = (actual_units / target_units * 100) if target_units else 0

    return {
        "stations": enriched,
        "bottleneck": bottleneck,
        "total_work_seconds": total_work_seconds,
        "target_units": target_units,
        "actual_units": actual_units,
        "gap_units": gap_units,
        "scenario": scenario,
        "max_capacity": max_capacity,
        "takt_utilization": takt_utilization,
    }


def best_one_operator_rebalance(stations: list[Station]) -> dict[str, Any] | None:
    if len(stations) < 2:
        return None
    current_bottleneck = min(stations, key=lambda s: s.capacity_per_hour)
    current_units = current_bottleneck.capacity_per_hour * AVAILABLE_SECONDS / 3600
    best = None

    for donor in stations:
        if donor.station_id == current_bottleneck.station_id or donor.operators <= 1:
            continue
        simulated = []
        for station in stations:
            operators = station.operators
            if station.station_id == donor.station_id:
                operators -= 1
            if station.station_id == current_bottleneck.station_id:
                operators += 1
            capacity = operators * 3600 / station.time_seconds if station.time_seconds > 0 else 0
            simulated.append((station, operators, capacity))

        new_bottleneck, _, new_capacity = min(simulated, key=lambda item: item[2])
        new_units = new_capacity * AVAILABLE_SECONDS / 3600
        improvement = new_units - current_units
        if improvement > 0 and (best is None or improvement > best["improvement_units"]):
            best = {
                "from_station": donor,
                "to_station": current_bottleneck,
                "new_bottleneck": new_bottleneck,
                "new_units": new_units,
                "improvement_units": improvement,
                "new_capacity": new_capacity,
            }
    return best


# ──────────────────────────────────────────────
#  Production data readers
# ──────────────────────────────────────────────
def read_balanceo() -> dict[str, list[dict]]:
    rows = read_csv_safe(CURATED_DIR / "balanceo_lineas.csv")
    result: dict[str, list[dict]] = {}
    for row in rows:
        linea = row.get("linea", "OTRO")
        result.setdefault(linea, []).append(row)
    return result


def read_plan_accion() -> list[dict]:
    rows = read_csv_safe(CURATED_DIR / "plan_accion.csv")
    if not rows:
        rows = _load_fallback("plan_accion.json")
    for row in rows:
        row.setdefault("status", "pendiente")
        try:
            row["num"] = int(float(row["num"]))
        except (ValueError, TypeError):
            pass
    return rows


def read_demanda() -> list[dict]:
    rows = read_csv_safe(CURATED_DIR / "demanda_afl.csv")
    if not rows:
        rows = _load_fallback("demanda.json")
    return rows


def read_bom(search: str = "", limit: int = 200) -> list[dict]:
    rows = read_csv_safe(CURATED_DIR / "bom_items.csv")
    if search:
        s = search.lower()
        rows = [
            r
            for r in rows
            if s in r.get("component_part", "").lower()
            or s in r.get("description", "").lower()
            or s in r.get("parent_part", "").lower()
        ]
    return rows[:limit]


def read_kanban() -> list[dict]:
    rows = read_csv_safe(CURATED_DIR / "kanban_notifications.csv")
    for r in rows:
        try:
            days = float(r.get("days_left", 0) or 0)
        except ValueError:
            days = 0
        if days <= 3:
            r["_urgency"] = "critical"
        elif days <= 7:
            r["_urgency"] = "warning"
        else:
            r["_urgency"] = "ok"
    return sorted(rows, key=lambda r: float(r.get("days_left", 9999) or 9999))


def read_desperdicios() -> list[dict]:
    rows = read_csv_safe(CURATED_DIR / "desperdicios.csv")
    return rows if rows else _load_fallback("desperdicios.json")


def read_throughput() -> list[dict]:
    rows = read_csv_safe(CURATED_DIR / "throughput_mejoras.csv")
    return rows if rows else _load_fallback("throughput.json")


def read_summary() -> dict:
    p = BASE_DIR / "adriana_projects" / "data" / "summary.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {}


# ──────────────────────────────────────────────
#  Template filters
# ──────────────────────────────────────────────
@app.template_filter("num")
def format_number(value: float, decimals: int = 1) -> str:
    try:
        return f"{float(value):,.{decimals}f}"
    except (TypeError, ValueError):
        return str(value)


@app.template_filter("pct")
def format_pct(value: float) -> str:
    try:
        return f"{float(value):.1f}%"
    except (TypeError, ValueError):
        return "—"


# ──────────────────────────────────────────────
#  Error handlers
# ──────────────────────────────────────────────
@app.errorhandler(404)
def not_found(e):
    return render_template("errors/404.html", title=APP_TITLE), 404


@app.errorhandler(500)
def server_error(e):
    logger.exception("Error 500")
    return render_template("errors/500.html", title=APP_TITLE), 500


# ──────────────────────────────────────────────
#  Auth routes
# ──────────────────────────────────────────────
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        users = _load_users()
        user_data = users.get(username)
        if user_data and check_password_hash(user_data["password_hash"], password):
            user = User(
                user_data["id"],
                user_data["username"],
                user_data["password_hash"],
                user_data.get("role", "user"),
            )
            login_user(user)
            flash(f"Bienvenido, {user.username}", "success")
            next_page = request.args.get("next")
            return redirect(next_page or url_for("dashboard"))
        flash("Usuario o contraseña incorrectos.", "danger")
    return render_template("login.html", title=APP_TITLE)


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Sesión cerrada.", "success")
    return redirect(url_for("login"))


# ──────────────────────────────────────────────
#  Routes — main dashboard
# ──────────────────────────────────────────────
@app.route("/")
@login_required
def dashboard() -> str:
    stations = read_stations()
    metrics = build_metrics(stations)
    summary = read_summary()
    return render_template(
        "dashboard.html",
        title=APP_TITLE,
        data_file=DATA_FILE,
        available_seconds=AVAILABLE_SECONDS,
        takt_seconds=TAKT_SECONDS,
        metrics=metrics,
        summary=summary,
        nav_active="dashboard",
    )


@app.route("/data.csv")
@login_required
def download_csv() -> Response:
    if not DATA_FILE.exists():
        return Response("CSV no encontrado\n", status=404, mimetype="text/plain")
    return send_file(DATA_FILE, as_attachment=True, download_name="stations.csv")


def _validate_station_csv(path: Path) -> tuple[bool, str]:
    """Validate that a CSV has the expected columns."""
    try:
        with path.open(newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames is None:
                return False, "El archivo está vacío o no tiene encabezados."
            headers = [h.strip().lower() for h in reader.fieldnames]
            required = {"station_name", "time_seconds", "operators"}
            missing = required - set(headers)
            if missing:
                return False, f"Faltan columnas requeridas: {', '.join(missing)}"
            # Try reading at least one row
            rows = list(reader)
            if not rows:
                return False, "El CSV no contiene filas de datos."
            return True, ""
    except Exception as exc:
        return False, f"Error leyendo CSV: {exc}"


@app.route("/upload", methods=["POST"])
@login_required
def upload_csv() -> Response:
    if UPLOAD_SECRET and request.form.get("upload_secret") != UPLOAD_SECRET:
        flash("Clave de actualización inválida.", "danger")
        return redirect(url_for("dashboard"))
    uploaded = request.files.get("csv_file")
    if not uploaded or not uploaded.filename.endswith(".csv"):
        flash("Sube un archivo CSV válido.", "danger")
        return redirect(url_for("dashboard"))

    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp_path = DATA_FILE.with_suffix(".tmp.csv")
    uploaded.save(temp_path)

    valid, msg = _validate_station_csv(temp_path)
    if not valid:
        temp_path.unlink(missing_ok=True)
        flash(f"CSV inválido: {msg}", "danger")
        return redirect(url_for("dashboard"))

    backup = DATA_FILE.with_suffix(".backup.csv")
    if DATA_FILE.exists():
        shutil.copyfile(DATA_FILE, backup)
    temp_path.replace(DATA_FILE)
    invalidate_csv_cache(DATA_FILE)
    logger.info("CSV actualizado por %s: %s", current_user.username, DATA_FILE)
    flash("CSV actualizado. El dashboard ya está usando la nueva data.", "success")
    return redirect(url_for("dashboard"))


# ──────────────────────────────────────────────
#  Routes — produccion
# ──────────────────────────────────────────────
@app.route("/produccion")
@login_required
def produccion() -> str:
    balanceo = read_balanceo()
    demanda = read_demanda()

    def line_kpis(rows: list[dict]) -> dict:
        if not rows:
            return {}
        cuellos = [
            r
            for r in rows
            if int(float(r.get("ct_actual", 0) or 0)) > int(float(r.get("takt", 0) or 0))
        ]
        max_gap = max(
            (int(float(r.get("ct_actual", 0) or 0)) - int(float(r.get("ct_meta", 0) or 0)) for r in rows),
            default=0,
        )
        total_ahorro = sum(int(float(r.get("ahorro_seg", 0) or 0)) for r in rows)
        return {
            "cuellos": len(cuellos),
            "max_gap_seg": max_gap,
            "total_ahorro_seg": total_ahorro,
            "estaciones": len(rows),
        }

    kpis = {linea: line_kpis(rows) for linea, rows in balanceo.items()}
    desperdicios = read_desperdicios()
    throughput = read_throughput()

    return render_template(
        "produccion.html",
        title=APP_TITLE,
        balanceo=balanceo,
        kpis=kpis,
        demanda=demanda,
        desperdicios=desperdicios,
        throughput=throughput,
        nav_active="produccion",
    )


# ──────────────────────────────────────────────
#  Routes — plan de accion
# ──────────────────────────────────────────────
@app.route("/plan")
@login_required
def plan() -> str:
    acciones = read_plan_accion()
    alta = [a for a in acciones if a.get("prioridad") == "ALTA"]
    media = [a for a in acciones if a.get("prioridad") == "MEDIA"]
    baja = [a for a in acciones if a.get("prioridad") == "BAJA"]
    lineas = sorted({a.get("linea", "") for a in acciones if a.get("linea")})
    return render_template(
        "plan.html",
        title=APP_TITLE,
        acciones=acciones,
        alta=alta,
        media=media,
        baja=baja,
        lineas=lineas,
        nav_active="plan",
    )


@app.route("/plan/<int:num>/status", methods=["POST"])
@login_required
def update_plan_status(num: int) -> Response:
    """AJAX endpoint: toggle status of a plan action."""
    new_status = request.json.get("status", "pendiente") if request.is_json else "pendiente"
    csv_path = CURATED_DIR / "plan_accion.csv"
    if not csv_path.exists():
        return jsonify({"ok": False, "error": "CSV not found"}), 404
    rows = read_csv_safe(csv_path)
    updated = False
    for row in rows:
        try:
            if int(float(row.get("num", 0))) == num:
                row["status"] = new_status
                updated = True
        except (ValueError, TypeError):
            pass
    if updated and rows:
        fieldnames = list(rows[0].keys())
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(rows)
        invalidate_csv_cache(csv_path)
    return jsonify({"ok": updated, "num": num, "status": new_status})


# ──────────────────────────────────────────────
#  Routes — partes / BOM
# ──────────────────────────────────────────────
@app.route("/partes")
@login_required
def partes() -> str:
    search = request.args.get("q", "").strip()
    bom = read_bom(search=search, limit=150)
    parts_count = len(read_csv_safe(CURATED_DIR / "parts.csv"))
    return render_template(
        "partes.html",
        title=APP_TITLE,
        bom=bom,
        search=search,
        parts_count=parts_count,
        nav_active="partes",
    )


# ──────────────────────────────────────────────
#  Routes — kanban
# ──────────────────────────────────────────────
@app.route("/kanban")
@login_required
def kanban() -> str:
    items = read_kanban()
    return render_template(
        "kanban.html",
        title=APP_TITLE,
        items=items,
        nav_active="kanban",
    )


# ──────────────────────────────────────────────
#  Routes — reporte ejecutivo (serve the HTML)
# ──────────────────────────────────────────────
@app.route("/reporte")
@login_required
def reporte() -> str:
    return render_template("reporte_ejecutivo_15k.html")


# ──────────────────────────────────────────────
#  API JSON
# ──────────────────────────────────────────────
@app.route("/api/metrics")
@login_required
def api_metrics() -> Response:
    stations = read_stations()
    m = build_metrics(stations)
    return jsonify(
        {
            "actual_units": round(m["actual_units"], 2),
            "target_units": round(m["target_units"], 2),
            "gap_units": round(m["gap_units"], 2),
            "takt_utilization": round(m["takt_utilization"], 1),
            "total_work_seconds": m["total_work_seconds"],
            "bottleneck": m["bottleneck"].station_name if m["bottleneck"] else None,
            "station_count": len(m["stations"]),
        }
    )


@app.route("/api/stations")
@login_required
def api_stations() -> Response:
    stations = read_stations()
    m = build_metrics(stations)
    return jsonify(
        [
            {
                "id": s["raw"].station_id,
                "name": s["raw"].station_name,
                "time_seconds": s["raw"].time_seconds,
                "operators": s["raw"].operators,
                "capacity_per_hour": round(s["raw"].capacity_per_hour, 2),
                "takt_gap": round(s["takt_gap"], 0),
                "takt_pct": round(s["takt_pct"], 1),
                "status": s["status"],
                "work_share": round(s["work_share"], 1),
            }
            for s in m["stations"]
        ]
    )


@app.route("/api/produccion")
@login_required
def api_produccion() -> Response:
    return jsonify(read_balanceo())


@app.route("/api/bom")
@login_required
def api_bom() -> Response:
    q = request.args.get("q", "")
    return jsonify(read_bom(search=q, limit=100))


@app.route("/api/summary")
@login_required
def api_summary() -> Response:
    return jsonify(read_summary())


@app.route("/api/demanda")
@login_required
def api_demanda() -> Response:
    return jsonify(read_demanda())


@app.route("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# ──────────────────────────────────────────────
#  Entry point
# ──────────────────────────────────────────────
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=True)
