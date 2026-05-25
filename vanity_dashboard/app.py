# =============================================================================
# Vanity Dashboard - Dashboard de Ventas y KPIs
# =============================================================================
# Servicio Flask que muestra KPIs de ventas, rendimiento de staff,
# ocupacion de salon y rentabilidad. Lee datos de CSV (all-data.csv)
# y configuracion JSON (staff_config.json, config.json).
#
# Autenticacion: SSO token via HQ Wrapper en /auth/hq
# Puerto: 5002 (default)
#
# Endpoints principales:
#   /api/kpi               - KPIs generales (ingresos, citas, ocupacion)
#   /api/sales_by_category  - Ventas por categoria
#   /api/sales_by_service    - Top servicios por ingreso
#   /api/sales_timeline      - Serie temporal mensual
#   /api/staff_performance   - Metricas por empleado
#   /api/salon/usage          - Uso de recursos del salon
#   /api/profitability        - Calculo de rentabilidad
#   /api/config               - Configuracion de porcentajes (GET/POST)
#   /api/filters              - Valores disponibles para filtros
# =============================================================================

import pandas as pd
import json
import os
import re
import secrets
import sys
import urllib.error
import urllib.request
from datetime import date, timedelta, datetime
from functools import wraps
from pathlib import Path

_common_dir = Path(__file__).resolve().parent
if not (_common_dir / "vanity_common").is_dir():
    _common_dir = _common_dir.parent
sys.path.insert(0, str(_common_dir))

from vanity_common.auth import load_user_from_session, login_required, require_permission
from vanity_common.session import SupabaseSessionInterface

from flask import Flask, flash, g, jsonify, redirect, render_template, request, session, url_for
from flask_cors import CORS
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
app.secret_key = os.getenv("VANITY_DASHBOARD_SECRET_KEY", "dev-dashboard-secret")
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["VANITY_HQ_PUBLIC_URL"] = os.getenv("VANITY_HQ_PUBLIC_URL", os.getenv("VANITY_HQ_URL", "http://127.0.0.1:5050"))
app.config["VANITY_HQ_SECRET_KEY"] = os.getenv("VANITY_HQ_SECRET_KEY", os.getenv("VANITY_DASHBOARD_SECRET_KEY", "dev-secret-change-me"))
app.config["VANITY_HQ_URL"] = os.getenv("VANITY_HQ_URL", "http://127.0.0.1:5050")
app.session_interface = SupabaseSessionInterface()
CORS(app)


@app.template_filter("num")
def format_number(value: float, decimals: int = 1) -> str:
    try:
        return f"{float(value):,.{decimals}f}"
    except (TypeError, ValueError):
        return str(value)


SYSTEM_KEY = "vanity_dashboard"
HQ_BASE_URL = os.getenv("VANITY_HQ_URL", "http://127.0.0.1:5050")
HQ_PUBLIC_URL = os.getenv("VANITY_HQ_PUBLIC_URL", HQ_BASE_URL)
HQ_SECRET_KEY = os.getenv("VANITY_HQ_SECRET_KEY", os.getenv("VANITY_DASHBOARD_SECRET_KEY", "dev-secret-change-me"))
HQ_TOKEN_MAX_AGE = int(os.getenv("VANITY_HQ_TOKEN_MAX_AGE", "43200"))

RAW_DATA_PATH = os.path.join(os.path.dirname(__file__), "all-data.csv")
STAFF_PATH = os.path.join(os.path.dirname(__file__), "staff_config.json")

RAW_COLUMNS = {
    "Ref. cita": "ref_cita",
    "Cliente": "cliente",
    "Miembro del equipo": "miembro_equipo",
    "Recurso": "recurso",
    "Estado": "estado",
    "Creada el día": "creada_el_dia",
    "Fecha programada": "fecha_programada",
    "Fecha de cancelación": "fecha_cancelacion",
    "Categoría": "categoria",
    "Servicio": "servicio",
    "Duración (min)": "duracion_original",
    "Franja horaria cita": "franja_horaria",
    "Creada por": "creada_por",
    "Cancelado por": "cancelado_por",
    "Centro": "centro",
    "Ventas netas": "ventas_netas",
    "Motivo de cancelación": "motivo_cancelacion",
    "Recargos aplicados": "recargos_aplicados",
    "Pagos por adelantado": "pagos_adelantado",
}

CATEGORY_MAP = {
    "💅MANOS": "Manos",
    "🦶🌸  PIES": "Pies",
    "✨ PESTAÑAS": "Pestañas",
    "✨CEJAS Y ROSTRO": "Cejas Y Rostro",
    "💄 MAKEUP & HAIR": "Makeup & Hair",
    "💆‍♀️ HAIR TREATMENTS": "Hair Treatments",
    "Aniversario Cima": "Manos",
    "ANIVERSARIO CIMA": "Manos",
    "Microblading": "Cejas Y Rostro",
    "💎 BODY/RELAX": "Body/Relax",
}

SERVICE_MAP = {
    "GELISH PARTY": "Gelish",
    "GELISH PARTY  (open house)": "Gelish",
    "HAPPY MONDAY (gelish manos)": "Gelish",
    "HAPPY WEDNESDAY (retoque de acrílico)": "Nail Refill ",
    "Acrylic Allure (Retoque de Acrílico + Gel) - 10% OFF": "Nail Refill ",
    "POLYGEL POWER DUO (baño de polygel)": "Polygel Extensions",
    "BASE RUUBER + GELISH": "Base rubber ",
    "UÑAS ACRILICAS": " Acrylic Extensions",
    "PERFECT LOOK (lash lifting + serum)": "Lash Lifting",
    "EXTENSONES DE PESTAÑAS": "Extensión de Pestañas (Elegant Lashes)",
    "CORTE SPA + TRATAMIENTO": "Corte SPA",
    "MASAJE RELAJANTE PROMO": "Masaje Relajante ",
}

PROMOTION_SERVICE_CATEGORIES = {
    "MANI + PEDI DELUXE": "Pies",
    "MANI + PEDI CLASSIC": "Pies",
    "UÑAS PRESS ON": "Manos",
    "GELISH MANOS Y PIES": "Pies",
}

MONTH_NAMES = {
    1: "Enero",
    2: "Febrero",
    3: "Marzo",
    4: "Abril",
    5: "Mayo",
    6: "Junio",
    7: "Julio",
    8: "Agosto",
    9: "Septiembre",
    10: "Octubre",
    11: "Noviembre",
    12: "Diciembre",
}

SEASONS = {
    1: "Invierno",
    2: "Invierno",
    3: "Primavera",
    4: "Primavera",
    5: "Primavera",
    6: "Verano",
    7: "Verano",
    8: "Verano",
    9: "Otoño",
    10: "Otoño",
    11: "Otoño",
    12: "Invierno",
}


def duration_to_minutes(duration):
    if pd.isna(duration):
        return 0
    hour_match = re.search(r"(\d+)\s*h", str(duration))
    min_match = re.search(r"(\d+)\s*min", str(duration))
    hours = int(hour_match.group(1)) if hour_match else 0
    minutes = int(min_match.group(1)) if min_match else 0
    return hours * 60 + minutes


def parse_datetime(series):
    parsed = pd.to_datetime(series, format="%d/%m/%y %H:%M:%S", errors="coerce")
    missing = parsed.isna() & series.notna()
    parsed.loc[missing] = pd.to_datetime(series[missing], format="%d %b %Y, %I:%M%p", errors="coerce")
    return parsed


def normalize_sales_data(path):
    sales = pd.read_csv(path)
    sales = sales.rename(columns=RAW_COLUMNS)

    for column in ["creada_el_dia", "fecha_programada", "fecha_cancelacion"]:
        sales[column] = parse_datetime(sales[column])

    sales["categoria"] = sales["categoria"].replace(CATEGORY_MAP)
    sales["servicio"] = sales["servicio"].replace(SERVICE_MAP)
    sales["categoria"] = sales["servicio"].str.strip().map(PROMOTION_SERVICE_CATEGORIES).fillna(sales["categoria"])
    sales.loc[sales["categoria"].str.contains("promo|paquete", case=False, na=False), "categoria"] = sales["servicio"].map({
        "Gelish": "Manos",
        "Nail Refill ": "Manos",
        "Polygel Extensions": "Manos",
        "Base rubber ": "Manos",
        " Acrylic Extensions": "Manos",
        "Lash Lifting": "Pestañas",
        "Extensión de Pestañas (Elegant Lashes)": "Pestañas",
        "Corte SPA": "Hair Treatments",
        "Masaje Relajante ": "Body/Relax",
    }).fillna(sales["categoria"])
    sales.loc[sales["servicio"].str.contains(r"^Retiro de uñas", case=False, na=False), "categoria"] = "Retiros"
    sales["ventas_netas"] = pd.to_numeric(sales["ventas_netas"], errors="coerce").fillna(0)
    sales["recargos_aplicados"] = pd.to_numeric(sales["recargos_aplicados"], errors="coerce").fillna(0)
    sales["pagos_adelantado"] = pd.to_numeric(sales["pagos_adelantado"], errors="coerce").fillna(0)

    if "tiempo_minutos" not in sales:
        sales["tiempo_minutos"] = sales["duracion_original"].apply(duration_to_minutes)

    scheduled = sales["fecha_programada"]
    sales["tiempo_anio"] = scheduled.dt.year.astype("Int64")
    sales["tiempo_mes_num"] = scheduled.dt.month.astype("Int64")
    sales["tiempo_mes"] = sales["tiempo_mes_num"].map(MONTH_NAMES)
    sales["tiempo_semana"] = scheduled.dt.isocalendar().week.astype("Int64")
    sales["tiempo_temporada"] = sales["tiempo_mes_num"].map(SEASONS)
    return sales


def load_sales_data():
    latest = normalize_sales_data(RAW_DATA_PATH)
    return latest, latest


df, latest_df = load_sales_data()

with open(STAFF_PATH) as f:
    staff_config = json.load(f)

real_staff_names = {s["nombre"] for s in staff_config}

def initials(name):
    return "".join(w[0].upper() for w in name.split() if w[0].isalpha())[:4]

def center_code(centro):
    if "Plaza O" in str(centro):
        return "O"
    elif "Plaza CIMA" in str(centro) or "CIMA" in str(centro):
        return "C"
    elif "Los Pinos" in str(centro):
        return "P"
    return "X"

# Build mapping: extra staff → EX-{INITIALS}-{CENTER}
staff_center_map = df.groupby("miembro_equipo")["centro"].agg(lambda x: x.mode().iloc[0] if not x.mode().empty else "").to_dict()

staff_rename = {}
for s in df["miembro_equipo"].unique():
    if s in real_staff_names or pd.isna(s):
        continue
    s_clean = s.strip() if isinstance(s, str) else s
    if s_clean in real_staff_names:
        continue
    init = initials(s_clean)
    center = center_code(staff_center_map.get(s_clean, ""))
    staff_rename[s_clean] = f"EX-{init}-{center}"

df["miembro_equipo"] = df["miembro_equipo"].map(lambda x: staff_rename.get(x.strip() if isinstance(x, str) else x, x))

STATUS_MAP = {
    "Nueva": "pending",
    "Confirmado": "confirmed",
    "Iniciada": "in_progress",
    "Completadas": "completed",
    "Cancelado": "cancelled",
    "Inasistencia": "no_show"
}
df["_status_normalized"] = df["estado"].map(STATUS_MAP).fillna("pending")

def filter_data(args):
    q = df.copy()
    if "year" in args and args["year"]:
        q = q[q["tiempo_anio"] == int(args["year"])]
    if "month" in args and args["month"]:
        q = q[q["tiempo_mes_num"] == int(args["month"])]
    if "categoria" in args:
        q = q[q["categoria"] == args["categoria"]]
    if "centro" in args:
        q = q[q["centro"] == args["centro"]]
    if "staff" in args:
        q = q[q["miembro_equipo"] == args["staff"]]
    if "periodo" in args and args["periodo"]:
        p = args["periodo"]
        hoy = date.today()
        dias = {"last_week": 7, "last_fortnight": 14, "last_month": 30, "last_quarter": 90, "last_semester": 180, "last_year": 365}
        if p in dias:
            since = hoy - timedelta(days=dias[p])
            q = q[q["fecha_programada"].dt.date >= since]
    return q

@app.before_request
def before_request():
    load_user_from_session()

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

# --- SSO Auth endpoint --------------------------------------------------------
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
    session["user_id"] = context["user"]["id"]
    return redirect(url_for("index"))

@app.route("/")
@login_required
def index():
    return render_template("dashboard.html")

@app.route("/healthz")
def healthz():
    return jsonify({"ok": True, "service": "dashboard"})

@app.route("/api/kpi")
@login_required
@require_permission("vanity_dashboard", "sales", "view")
def api_kpi():
    q = filter_data(request.args)
    q_fin = q[q["_status_normalized"].isin(["completed", "cancelled"])]
    hoy = date.today()
    q_hoy = q[q["fecha_programada"].dt.date == hoy]
    q_hoy_fin = q_hoy[q_hoy["_status_normalized"].isin(["completed", "cancelled"])]

    q_completed = q_fin[q_fin["_status_normalized"] == "completed"]
    q_hoy_completed = q_hoy_fin[q_hoy_fin["_status_normalized"] == "completed"]

    ventas_hoy = q_hoy_completed["ventas_netas"].sum()
    citas_hoy = len(q_hoy_fin)
    ticket_prom_hoy = round(ventas_hoy / len(q_hoy_completed), 2) if len(q_hoy_completed) > 0 else 0

    total_citas = len(q_fin)
    total_completadas = len(q_completed)
    total_ventas = q_completed["ventas_netas"].sum()
    canceladas = len(q_fin[q_fin["_status_normalized"] == "cancelled"])
    cancel_rate = round(canceladas / total_citas * 100, 1) if total_citas > 0 else 0

    clientes_unicos = q_fin["cliente"].nunique()
    clientes_hoy = q_hoy_fin["cliente"].nunique()

    ticket_prom_total = round(total_ventas / total_completadas, 2) if total_completadas > 0 else 0

    slots_dia = 48
    ocupacion = round(min(len(q_hoy) / slots_dia * 100, 100), 1)

    rebooking = q_fin[q_fin["cliente"].duplicated(keep=False)]
    rebooking_rate = round(len(rebooking) / total_citas * 100, 1) if total_citas > 0 else 0

    completadas_pct = round(total_completadas / total_citas * 100, 1) if total_citas > 0 else 0
    oportunidad_perdida = float(q_fin[q_fin["_status_normalized"] == "cancelled"]["ventas_netas"].sum())
    oportunidad_perdida_hoy = float(q_hoy_fin[q_hoy_fin["_status_normalized"] == "cancelled"]["ventas_netas"].sum())

    return jsonify({
        "ventas_hoy": float(ventas_hoy),
        "ventas_hoy_fmt": f"${float(ventas_hoy):,.0f}",
        "citas_hoy": citas_hoy,
        "total_ventas": float(total_ventas),
        "total_ventas_fmt": f"${float(total_ventas):,.0f}",
        "total_citas": total_citas,
        "total_completadas": total_completadas,
        "ticket_promedio_hoy": ticket_prom_hoy,
        "ticket_promedio_hoy_fmt": f"${ticket_prom_hoy:,.0f}",
        "ticket_promedio": ticket_prom_total,
        "ticket_promedio_fmt": f"${ticket_prom_total:,.0f}",
        "ocupacion": ocupacion,
        "ocupacion_fmt": f"{ocupacion}%",
        "rebooking_rate": rebooking_rate,
        "rebooking_rate_fmt": f"{rebooking_rate}%",
        "cancelaciones": canceladas,
        "cancel_rate": cancel_rate,
        "cancel_rate_fmt": f"{cancel_rate}%",
        "completadas_pct": completadas_pct,
        "completadas_pct_fmt": f"{completadas_pct}%",
        "oportunidad_perdida": oportunidad_perdida,
        "oportunidad_perdida_fmt": f"${oportunidad_perdida:,.0f}",
        "oportunidad_perdida_hoy": oportunidad_perdida_hoy,
        "oportunidad_perdida_hoy_fmt": f"${oportunidad_perdida_hoy:,.0f}",
        "clientes_nuevos": clientes_hoy,
        "clientes_totales": clientes_unicos,
    })

@app.route("/api/sales_by_category")
@login_required
@require_permission("vanity_dashboard", "sales", "view")
def api_sales_category():
    q = filter_data(request.args)
    qs = q[q["_status_normalized"] == "completed"]
    g = qs.groupby("categoria")["ventas_netas"].sum().sort_values(ascending=False).reset_index()
    return jsonify({"labels": g["categoria"].tolist(), "values": g["ventas_netas"].round(2).tolist()})

@app.route("/api/sales_by_service")
@login_required
@require_permission("vanity_dashboard", "sales", "view")
def api_sales_service():
    q = filter_data(request.args)
    qs = q[q["_status_normalized"] == "completed"]
    limit = request.args.get("limit", 15, type=int)
    g = qs.groupby("servicio").agg(
        ventas=("ventas_netas", "sum"),
        citas=("ref_cita", "count"),
        ticket_prom=("ventas_netas", "mean"),
        tiempo_prom=("tiempo_minutos", "mean")
    ).reset_index().sort_values("ventas", ascending=False)
    if limit:
        g = g.head(limit)
    return jsonify({
        "labels": g["servicio"].tolist(),
        "values": g["ventas"].round(2).tolist(),
        "citas": g["citas"].tolist(),
        "ticket_prom": g["ticket_prom"].round(2).tolist(),
        "tiempo_prom": g["tiempo_prom"].round(1).tolist()
    })

@app.route("/api/services/all")
@login_required
@require_permission("vanity_dashboard", "sales", "view")
def api_services_all():
    q = filter_data(request.args)
    qs = q[q["_status_normalized"] == "completed"]
    g = qs.groupby("servicio").agg(
        ventas=("ventas_netas", "sum"),
        citas=("ref_cita", "count"),
        ticket_prom=("ventas_netas", "mean"),
        tiempo_prom=("tiempo_minutos", "mean"),
        categoria=("categoria", "first")
    ).reset_index().sort_values("ventas", ascending=False)
    g["ventas"] = g["ventas"].round(2)
    g["ticket_prom"] = g["ticket_prom"].round(2)
    g["tiempo_prom"] = g["tiempo_prom"].round(1)
    return jsonify(g.to_dict(orient="records"))

@app.route("/api/sales_timeline")
@login_required
@require_permission("vanity_dashboard", "sales", "view")
def api_sales_timeline():
    q = filter_data(request.args)
    qs = q[q["_status_normalized"] == "completed"]
    group_by = request.args.get("group")
    if group_by == "centro":
        g = qs.groupby(["centro", "tiempo_anio", "tiempo_mes_num", "tiempo_mes"])["ventas_netas"].sum().reset_index()
        g = g.sort_values(["tiempo_anio", "tiempo_mes_num"])
        g["label"] = g["tiempo_mes"] + " " + g["tiempo_anio"].astype(str)
        all_labels = sorted(g["label"].unique(), key=lambda x: list(g["label"].unique()).index(x))
        datasets = {}
        for _, r in g.iterrows():
            c = r["centro"]
            if c not in datasets:
                datasets[c] = {c: 0 for c in all_labels}
            datasets[c][r["label"]] = r["ventas_netas"]
        result = {"labels": all_labels, "datasets": []}
        for centro, data in datasets.items():
            result["datasets"].append({"label": centro, "values": [round(data[l], 2) for l in all_labels]})
        return jsonify(result)
    g = qs.groupby(["tiempo_anio", "tiempo_mes_num", "tiempo_mes"])["ventas_netas"].sum().reset_index()
    g = g.sort_values(["tiempo_anio", "tiempo_mes_num"])
    g["label"] = g["tiempo_mes"] + " " + g["tiempo_anio"].astype(str)
    return jsonify({"labels": g["label"].tolist(), "values": g["ventas_netas"].round(2).tolist()})

@app.route("/api/appointments_by_staff")
@login_required
@require_permission("vanity_dashboard", "appointments", "view")
def api_appointments_staff():
    q = filter_data(request.args)
    qs = q[q["_status_normalized"] == "completed"]
    g = qs.groupby("miembro_equipo").size().sort_values(ascending=False).head(15).reset_index(name="count")
    return jsonify({"labels": g["miembro_equipo"].tolist(), "values": g["count"].tolist()})

@app.route("/api/staff_performance")
@login_required
@require_permission("vanity_dashboard", "staff_performance", "view")
def api_staff_performance():
    q = filter_data(request.args)
    qs = q[q["_status_normalized"] == "completed"]
    g = qs.groupby("miembro_equipo").agg(
        citas=("ref_cita", "count"),
        ventas=("ventas_netas", "sum"),
        ticket_prom=("ventas_netas", "mean"),
        canceladas=("_status_normalized", lambda x: (x == "cancelled").sum())
    ).reset_index()
    range_df = qs.groupby("miembro_equipo").agg(
        fecha_min=("fecha_programada", "min"),
        fecha_max=("fecha_programada", "max"),
        dias_activos=("fecha_programada", lambda x: x.dt.date.nunique())
    ).reset_index()
    g = g.merge(range_df, on="miembro_equipo", how="left")
    g["ventas"] = g["ventas"].round(2)
    g["ticket_prom"] = g["ticket_prom"].round(2)
    g["semanas_activas"] = ((g["fecha_max"] - g["fecha_min"]).dt.days / 7).clip(lower=1).fillna(1)
    g["avg_diario"] = (g["citas"] / g["dias_activos"].replace(0, 1)).round(1)
    g["avg_semanal"] = (g["citas"] / g["semanas_activas"]).round(1)
    g["es_real"] = g["miembro_equipo"].isin(real_staff_names)
    g = g.drop(columns=["fecha_min", "fecha_max", "semanas_activas"])
    g = g.sort_values("ventas", ascending=False)
    return jsonify(g.to_dict(orient="records"))

@app.route("/api/staff_by_branch")
@login_required
@require_permission("vanity_dashboard", "staff_performance", "view")
def api_staff_by_branch():
    q = filter_data(request.args)
    qs = q[q["_status_normalized"] == "completed"]
    g = qs.groupby(["centro", "miembro_equipo"]).agg(
        citas=("ref_cita", "count"),
        ventas=("ventas_netas", "sum"),
        ticket_prom=("ventas_netas", "mean"),
        minutos=("tiempo_minutos", "sum"),
        canceladas=("_status_normalized", lambda x: (x == "cancelled").sum())
    ).reset_index()
    g["ventas"] = g["ventas"].round(2)
    g["ticket_prom"] = g["ticket_prom"].round(2)
    g["horas"] = (g["minutos"] / 60).round(1)
    semanas = max((q["fecha_programada"].max() - q["fecha_programada"].min()).days / 7, 1)
    max_horas = 48 * semanas
    g["utilizacion"] = (g["horas"] / max_horas * 100).round(1).clip(upper=100)
    g = g.sort_values(["centro", "ventas"], ascending=[True, False])
    g["es_real"] = g["miembro_equipo"].isin(real_staff_names)
    return jsonify(g.to_dict(orient="records"))

@app.route("/api/staff/profiles")
@login_required
@require_permission("vanity_dashboard", "staff_performance", "view")
def api_staff_profiles():
    q = filter_data(request.args)
    qs = q[q["_status_normalized"] == "completed"]
    q_final = q[q["_status_normalized"].isin(["completed", "cancelled"])]
    perf = qs.groupby("miembro_equipo").agg(
        servicios=("ref_cita", "count"),
        ventas=("ventas_netas", "sum"),
        ticket_prom=("ventas_netas", "mean"),
        minutos_servicio=("tiempo_minutos", "sum")
    ).reset_index()
    status_perf = q_final.groupby("miembro_equipo").agg(
        canceladas=("_status_normalized", lambda x: (x == "cancelled").sum()),
        fecha_inicio=("fecha_programada", "min"),
        fecha_fin=("fecha_programada", "max")
    ).reset_index()
    perf = perf.merge(status_perf, on="miembro_equipo", how="outer")
    for column in ["servicios", "ventas", "ticket_prom", "minutos_servicio", "canceladas"]:
        perf[column] = perf[column].fillna(0)
    perf["total_servicios"] = perf["servicios"] + perf["canceladas"]
    perf["cancel_rate"] = (perf["canceladas"] / perf["total_servicios"].replace(0, 1) * 100).round(1)
    perf["semanas_activas"] = ((perf["fecha_fin"] - perf["fecha_inicio"]).dt.days / 7).clip(lower=1).fillna(1)
    perf["horas_capacidad"] = perf["semanas_activas"] * 48
    perf["horas_servicio"] = (perf["minutos_servicio"] / 60).round(1)
    perf["horas_muertas"] = (perf["horas_capacidad"] - perf["horas_servicio"]).clip(lower=0).round(1)
    perf["tiempo_muerto_pct"] = (perf["horas_muertas"] / perf["horas_capacidad"].replace(0, 1) * 100).round(1).clip(upper=100)
    perf["ventas"] = perf["ventas"].round(2)
    perf["ticket_prom"] = perf["ticket_prom"].round(2)
    perf = perf.drop(columns=["fecha_inicio", "fecha_fin", "semanas_activas"])
    result = []
    for s in staff_config:
        row = perf[perf["miembro_equipo"] == s["nombre"]]
        if len(row) > 0:
            r = row.iloc[0].to_dict()
        else:
            r = {
                "miembro_equipo": s["nombre"],
                "servicios": 0,
                "ventas": 0,
                "ticket_prom": 0,
                "canceladas": 0,
                "cancel_rate": 0,
                "horas_muertas": 0,
                "tiempo_muerto_pct": 0
            }
        r["contacto"] = s["contacto"]
        r["telefono"] = s["telefono"]
        r["rol"] = s["rol"]
        r["alias"] = s.get("alias", "")
        r["rating"] = s["rating"]
        r["permiso"] = s["permiso"]
        result.append(r)
    return jsonify(result)

@app.route("/api/salon/usage")
@login_required
@require_permission("vanity_dashboard", "inventory", "view")
def api_salon_usage():
    q = filter_data(request.args)
    qs = q[q["_status_normalized"] == "completed"]
    today = date.today()
    q_today = q[q["fecha_programada"].dt.date == today]

    recursos_unicos = df["recurso"].dropna().unique()
    total_recursos = len(recursos_unicos)

    citas_hoy = len(q_today)
    recursos_usados_hoy = q_today["recurso"].dropna().nunique()

    g_recurso = qs.groupby("recurso").agg(
        citas=("ref_cita", "count"),
        tiempo_total=("tiempo_minutos", "sum"),
        ventas=("ventas_netas", "sum")
    ).reset_index().sort_values("citas", ascending=False)

    g_tipo = q.groupby("recurso").size().reset_index(name="count")
    g_tipo["tipo"] = g_tipo["recurso"].apply(lambda r: "Mesa" if "Mesa" in str(r) else ("Sillón" if "Sillón" in str(r) or "Sillon" in str(r) or "Sillón" in str(r) else "Otro"))
    g_tipo = g_tipo.groupby("tipo")["count"].sum().reset_index()

    horas_pico = q.copy()
    horas_pico["hora"] = horas_pico["franja_horaria"].str.split("-").str[0].str.split(":").str[0]
    g_horas = horas_pico.groupby("hora").size().reset_index(name="count").sort_values("count", ascending=False).head(10)

    return jsonify({
        "recursos_totales": total_recursos,
        "recursos_usados_hoy": int(recursos_usados_hoy),
        "citas_hoy": citas_hoy,
        "recursos_top": [{"recurso": r["recurso"], "citas": int(r["citas"]), "horas": int(r["tiempo_total"] / 60), "ventas": round(float(r["ventas"]), 2)} for _, r in g_recurso.head(20).iterrows()],
        "por_tipo": [{"tipo": r["tipo"], "citas": int(r["count"])} for _, r in g_tipo.iterrows()],
        "horas_pico": [{"hora": r["hora"] + ":00", "citas": int(r["count"])} for _, r in g_horas.iterrows()]
    })

@app.route("/api/salon/resources")
@login_required
@require_permission("vanity_dashboard", "inventory", "view")
def api_salon_resources():
    q = filter_data(request.args)
    qs = q[q["_status_normalized"] == "completed"]
    g = qs.groupby(["recurso", "miembro_equipo", "centro"]).agg(
        citas=("ref_cita", "count"),
        tiempo=("tiempo_minutos", "sum"),
        ventas=("ventas_netas", "sum")
    ).reset_index()
    result = []
    for (recurso, centro), group in g.groupby(["recurso", "centro"]):
        rows = group.sort_values("citas", ascending=False).head(5).to_dict(orient="records")
        total_citas = int(group["citas"].sum())
        total_tiempo = int(group["tiempo"].sum())
        total_ventas = round(float(group["ventas"].sum()), 2)
        result.append({
            "recurso": recurso,
            "centro": centro,
            "total_citas": total_citas,
            "total_horas": round(total_tiempo / 60, 1),
            "total_ventas": total_ventas,
            "staff": [{"nombre": r["miembro_equipo"], "citas": int(r["citas"]), "horas": round(r["tiempo"] / 60, 1)} for r in rows]
        })
    if request.args.get("group") == "centro":
        cm = {}
        for r in result:
            c = r["centro"]
            if c not in cm:
                cm[c] = {"centro": c, "subtotal_citas": 0, "subtotal_horas": 0, "subtotal_ventas": 0, "resources": []}
            cm[c]["subtotal_citas"] += r["total_citas"]
            cm[c]["subtotal_horas"] += r["total_horas"]
            cm[c]["subtotal_ventas"] += r["total_ventas"]
            cm[c]["resources"].append(r)
        return jsonify({"grouped": True, "data": [cm[c] for c in sorted(cm.keys())]})
    result.sort(key=lambda r: (r["centro"], r["recurso"]))
    return jsonify(result)

@app.route("/api/salon/by_branch")
@login_required
@require_permission("vanity_dashboard", "inventory", "view")
def api_salon_by_branch():
    q = filter_data(request.args)
    qs = q[q["_status_normalized"] == "completed"]
    g = qs.groupby("centro").agg(
        citas=("ref_cita", "count"),
        ventas=("ventas_netas", "sum"),
        clientes=("cliente", "nunique"),
        ticket_prom=("ventas_netas", "mean"),
        minutos=("tiempo_minutos", "sum"),
        recursos=("recurso", "nunique"),
        canceladas=("_status_normalized", lambda x: (x == "cancelled").sum())
    ).reset_index()
    g["ventas"] = g["ventas"].round(2)
    g["ticket_prom"] = g["ticket_prom"].round(2)
    g["horas"] = (g["minutos"] / 60).round(1)
    g["roi_approx"] = (g["ventas"] / g["minutos"].replace(0, 1) * 60).round(2)
    g = g.sort_values("ventas", ascending=False)
    return jsonify(g.to_dict(orient="records"))

@app.route("/api/salon/uptime")
@login_required
@require_permission("vanity_dashboard", "inventory", "view")
def api_salon_uptime():
    q = filter_data(request.args)
    q_final = q[q["_status_normalized"].isin(["completed", "cancelled"])]
    qs = q[q["_status_normalized"] == "completed"]

    perf = qs.groupby("miembro_equipo").agg(
        servicios=("ref_cita", "count"),
        minutos_servicio=("tiempo_minutos", "sum")
    ).reset_index()

    status_perf = q_final.groupby("miembro_equipo").agg(
        canceladas=("_status_normalized", lambda x: (x == "cancelled").sum()),
        fecha_inicio=("fecha_programada", "min"),
        fecha_fin=("fecha_programada", "max")
    ).reset_index()

    perf = perf.merge(status_perf, on="miembro_equipo", how="outer")
    for col in ["servicios", "minutos_servicio", "canceladas"]:
        perf[col] = perf[col].fillna(0)
    perf["total_servicios"] = perf["servicios"] + perf["canceladas"]
    perf["semanas_activas"] = ((perf["fecha_fin"] - perf["fecha_inicio"]).dt.days / 7).clip(lower=1).fillna(1)
    perf["horas_capacidad"] = perf["semanas_activas"] * 48
    perf["horas_servicio"] = (perf["minutos_servicio"] / 60).round(1)
    perf["horas_muertas"] = (perf["horas_capacidad"] - perf["horas_servicio"]).clip(lower=0).round(1)

    total_capacidad = perf["horas_capacidad"].sum()
    total_servicio = perf["horas_servicio"].sum()
    total_muertas = perf["horas_muertas"].sum()

    uptime_pct = round(total_servicio / total_capacidad * 100, 1) if total_capacidad > 0 else 0
    downtime_pct = round(total_muertas / total_capacidad * 100, 1) if total_capacidad > 0 else 0

    return jsonify({
        "total_horas_capacidad": round(total_capacidad, 1),
        "total_horas_servicio": round(total_servicio, 1),
        "total_horas_muertas": round(total_muertas, 1),
        "uptime_pct": uptime_pct,
        "downtime_pct": downtime_pct,
        "uptime_fmt": f"{uptime_pct}%",
        "downtime_fmt": f"{downtime_pct}%"
    })

@app.route("/api/appointments")
@login_required
@require_permission("vanity_dashboard", "appointments", "view")
def api_appointments():
    q = filter_data(request.args)
    q = q.sort_values("fecha_programada", ascending=False)
    cols = ["ref_cita", "cliente", "servicio", "miembro_equipo", "estado", "_status_normalized", "ventas_netas", "fecha_programada", "franja_horaria"]
    limit = request.args.get("limit", 100, type=int)
    data = q[cols].head(limit).to_dict(orient="records")
    for r in data:
        if pd.notna(r["fecha_programada"]):
            r["fecha_programada"] = r["fecha_programada"].strftime("%d/%m/%y")
        else:
            r["fecha_programada"] = ""
        r["ventas_netas"] = float(r["ventas_netas"]) if pd.notna(r["ventas_netas"]) else 0
    return jsonify(data)

@app.route("/api/appointments/stats")
@login_required
@require_permission("vanity_dashboard", "appointments", "view")
def api_appointments_stats():
    q = filter_data(request.args)
    g = q.groupby("_status_normalized").size().reset_index(name="count")
    total = int(g["count"].sum())
    result = {"total": total}
    for _, r in g.iterrows():
        result[r["_status_normalized"]] = int(r["count"])
    for s in ["pending", "confirmed", "in_progress", "completed", "cancelled", "no_show"]:
        if s not in result:
            result[s] = 0
    return jsonify(result)

@app.route("/api/cancellations")
@login_required
@require_permission("vanity_dashboard", "appointments", "view")
def api_cancellations():
    q = filter_data(request.args)
    g = q.groupby("miembro_equipo").agg(
        completadas=("_status_normalized", lambda x: (x == "completed").sum()),
        canceladas=("_status_normalized", lambda x: (x == "cancelled").sum()),
        ingresos_completadas=("ventas_netas", lambda x: x[q.loc[x.index, "_status_normalized"] == "completed"].sum()),
        ingresos_perdidos=("ventas_netas", lambda x: x[q.loc[x.index, "_status_normalized"] == "cancelled"].sum())
    ).reset_index()
    g["total"] = g["completadas"] + g["canceladas"]
    g["cancel_rate"] = (g["canceladas"] / g["total"] * 100).round(1)
    g["ingresos_completadas"] = g["ingresos_completadas"].round(2)
    g["ingresos_perdidos"] = g["ingresos_perdidos"].round(2)
    g["lucro_cesante"] = (g["ingresos_perdidos"] * 0.475).round(2)
    g["es_real"] = g["miembro_equipo"].isin(real_staff_names)
    g = g.sort_values("canceladas", ascending=False)
    return jsonify(g.to_dict(orient="records"))

@app.route("/api/profitability")
@login_required
@require_permission("vanity_dashboard", "reports", "view")
def api_profitability():
    cfg = load_config()
    ops_pct = cfg.get("costos_operativos_porcentaje", 30) / 100.0
    nom_pct = cfg.get("nomina_porcentaje", 22.5) / 100.0
    margen_pct = round((1 - ops_pct - nom_pct) * 100, 1)
    q = filter_data(request.args)
    qc = q[q["_status_normalized"] == "completed"]
    total_ingresos = float(qc["ventas_netas"].sum())
    total_citas = int(len(qc))
    total_costos_ops = round(total_ingresos * ops_pct, 2)
    total_nomina = round(total_ingresos * nom_pct, 2)
    total_utilidad = round(total_ingresos - total_costos_ops - total_nomina, 2)
    margen = round((total_utilidad / total_ingresos * 100) if total_ingresos else 0, 1)

    by_staff = qc.groupby("miembro_equipo").agg(
        citas=("ventas_netas", "count"),
        ingresos=("ventas_netas", "sum")
    ).reset_index()
    by_staff["ingresos"] = by_staff["ingresos"].round(2)
    by_staff["costos_ops"] = (by_staff["ingresos"] * ops_pct).round(2)
    by_staff["nomina"] = (by_staff["ingresos"] * nom_pct).round(2)
    by_staff["utilidad"] = (by_staff["ingresos"] - by_staff["costos_ops"] - by_staff["nomina"]).round(2)
    by_staff["margen"] = margen_pct
    by_staff = by_staff.sort_values("utilidad", ascending=False)
    by_staff["es_real"] = by_staff["miembro_equipo"].isin(real_staff_names)

    by_branch = qc.groupby("centro").agg(
        citas=("ventas_netas", "count"),
        ingresos=("ventas_netas", "sum")
    ).reset_index()
    by_branch["ingresos"] = by_branch["ingresos"].round(2)
    by_branch["costos_ops"] = (by_branch["ingresos"] * ops_pct).round(2)
    by_branch["nomina"] = (by_branch["ingresos"] * nom_pct).round(2)
    by_branch["utilidad"] = (by_branch["ingresos"] - by_branch["costos_ops"] - by_branch["nomina"]).round(2)
    by_branch["margen"] = margen_pct
    by_branch = by_branch.sort_values("utilidad", ascending=False)

    return jsonify({
        "total": {
            "ingresos": total_ingresos,
            "citas": total_citas,
            "costos_ops": total_costos_ops,
            "nomina": total_nomina,
            "utilidad": total_utilidad,
            "margen": margen
        },
        "by_staff": by_staff.to_dict(orient="records"),
        "by_branch": by_branch.to_dict(orient="records")
    })

@app.route("/api/report/summary")
@login_required
@require_permission("vanity_dashboard", "reports", "view")
def api_report_summary():
    now_args = request.args
    if "periodo" in now_args and now_args["periodo"]:
        p = now_args["periodo"]
        dias = {"last_week": 7, "last_fortnight": 14, "last_month": 30, "last_quarter": 90, "last_semester": 180, "last_year": 365}
        if p in dias:
            d = dias[p]
            hoy = date.today()
            inicio_actual = hoy - timedelta(days=d)
            fin_actual = hoy
            inicio_prev = inicio_actual - timedelta(days=d)
            q_actual = filter_data_static(inicio_actual, fin_actual, now_args)
            q_prev = filter_data_static(inicio_prev, inicio_actual, now_args)
    else:
        q_actual = filter_data(now_args)
        q_prev = None

    def calc_stats(df_filtered):
        if df_filtered is None or len(df_filtered) == 0:
            return {"ingresos": 0, "citas": 0, "completadas": 0, "canceladas": 0, "gasto_prom": 0}
        c = df_filtered[df_filtered["_status_normalized"] == "completed"]
        ca = df_filtered[df_filtered["_status_normalized"] == "cancelled"]
        ingresos = float(c["ventas_netas"].sum())
        citas = int(len(c))
        canceladas = int(len(ca))
        return {
            "ingresos": round(ingresos, 2),
            "citas": citas,
            "canceladas": canceladas,
            "gasto_prom": round(ingresos / citas, 2) if citas else 0
        }

    ahora = calc_stats(q_actual)
    prev = calc_stats(q_prev) if q_prev is not None else None

    if prev and prev["ingresos"]:
        def pct(a, b):
            return round((a - b) / b * 100, 1) if b else 0
        comparacion = {
            "ingresos": {"actual": ahora["ingresos"], "anterior": prev["ingresos"], "cambio": pct(ahora["ingresos"], prev["ingresos"])},
            "citas": {"actual": ahora["citas"], "anterior": prev["citas"], "cambio": pct(ahora["citas"], prev["citas"])},
            "canceladas": {"actual": ahora["canceladas"], "anterior": prev["canceladas"], "cambio": pct(ahora["canceladas"], prev["canceladas"])},
            "gasto_prom": {"actual": ahora["gasto_prom"], "anterior": prev["gasto_prom"], "cambio": pct(ahora["gasto_prom"], prev["gasto_prom"])}
        }
    else:
        comparacion = None

    return jsonify({"ahora": ahora, "anterior": prev, "comparacion": comparacion})

def filter_data_static(desde, hasta, args):
    q = df.copy()
    if "year" in args and args["year"]:
        q = q[q["tiempo_anio"] == int(args["year"])]
    if "month" in args and args["month"]:
        q = q[q["tiempo_mes_num"] == int(args["month"])]
    if "centro" in args:
        q = q[q["centro"] == args["centro"]]
    if "staff" in args:
        q = q[q["miembro_equipo"] == args["staff"]]
    if "categoria" in args:
        q = q[q["categoria"] == args["categoria"]]
    q = q[(q["fecha_programada"].dt.date >= desde) & (q["fecha_programada"].dt.date < hasta)]
    return q

# ---- Config ----
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")

def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH) as f:
            return json.load(f)
    return {"comision_porcentaje": 10, "costos_operativos_porcentaje": 30, "nomina_porcentaje": 22.5}

@app.route("/api/config", methods=["GET"])
@login_required
@require_permission("vanity_dashboard", "settings", "view")
def api_config_get():
    cfg = load_config()
    cfg["staff"] = staff_config
    return jsonify(cfg)

@app.route("/api/config", methods=["POST"])
@login_required
@require_permission("vanity_dashboard", "settings", "configure")
def api_config_set():
    cfg = load_config()
    data = request.get_json()
    for k in ["comision_porcentaje", "costos_operativos_porcentaje", "nomina_porcentaje"]:
        if k in data:
            cfg[k] = float(data[k])
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)
    return jsonify({"ok": True, "config": cfg})

# ---- Nueva Cita ----
CITAS_MANUAL_PATH = os.path.join(os.path.dirname(__file__), "appointments_manual.json")

def load_citas_manual():
    if os.path.exists(CITAS_MANUAL_PATH):
        with open(CITAS_MANUAL_PATH) as f:
            return json.load(f)
    return []

@app.route("/api/appointments/create", methods=["POST"])
@login_required
@require_permission("vanity_dashboard", "appointments", "create")
def api_create_cita():
    data = request.get_json()
    citas = load_citas_manual()
    next_id = max([c["id"] for c in citas], default=100000) + 1
    cita = {
        "id": next_id,
        "cliente": data.get("cliente", ""),
        "servicio": data.get("servicio", ""),
        "miembro_equipo": data.get("staff", ""),
        "centro": data.get("centro", ""),
        "fecha": data.get("fecha", ""),
        "hora": data.get("hora", ""),
        "notas": data.get("notas", ""),
        "estado": "confirmed",
        "created_at": datetime.now().isoformat()
    }
    citas.insert(0, cita)
    with open(CITAS_MANUAL_PATH, "w") as f:
        json.dump(citas, f, indent=2, ensure_ascii=False)
    return jsonify({"ok": True, "cita": cita})

@app.route("/api/filters")
@login_required
@require_permission("vanity_dashboard", "sales", "view")
def api_filters():
    return jsonify({
        "years": sorted(df["tiempo_anio"].unique().astype(int).tolist()),
        "categorias": sorted(df["categoria"].dropna().unique().tolist()),
        "centros": sorted(df["centro"].dropna().unique().tolist()),
        "staff": sorted(df["miembro_equipo"].dropna().unique().tolist()),
        "meses": [{"num": int(r["tiempo_mes_num"]), "nombre": r["tiempo_mes"]} for _, r in df[["tiempo_mes_num", "tiempo_mes"]].drop_duplicates().sort_values("tiempo_mes_num").iterrows()],
        "data_corte": latest_df["fecha_programada"].max().strftime("%d/%m/%Y") if latest_df["fecha_programada"].notna().any() else ""
    })

if __name__ == "__main__":
    os.makedirs(os.path.join(os.path.dirname(__file__), "templates"), exist_ok=True)
    port = int(os.environ.get("PORT", 5001))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(debug=debug, host="0.0.0.0", port=port)
