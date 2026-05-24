"""Cadrex — Analytics & ROI Justification Engine."""
from flask import jsonify, render_template
from . import kadrix_bp
from .db import query


# ──────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────
def _lines():
    return query("SELECT * FROM kadrix_lines WHERE active = 1 ORDER BY code")


def _stations(line_id=None):
    sql = "SELECT s.*, l.code AS line_code FROM kadrix_stations s JOIN kadrix_lines l ON s.line_id = l.id WHERE s.active = 1"
    params = ()
    if line_id:
        sql += " AND s.line_id = %s"
        params = (line_id,)
    sql += " ORDER BY l.code, s.code"
    return query(sql, params)


def _baseline(line_id=None):
    sql = """
    SELECT m.*, s.name AS station_name, l.code AS line_code
    FROM kadrix_baseline_metrics m
    JOIN kadrix_lines l ON m.line_id = l.id
    LEFT JOIN kadrix_stations s ON m.station_id = s.id
    WHERE m.metric_type = 'cycle_time'
    """
    params = ()
    if line_id:
        sql += " AND m.line_id = %s"
        params = (line_id,)
    sql += " ORDER BY l.code, m.value DESC"
    return query(sql, params)


def _improvements(line_id=None, status=None):
    sql = """
    SELECT i.*, l.code AS line_code, s.name AS station_name
    FROM kadrix_improvements i
    LEFT JOIN kadrix_lines l ON i.line_id = l.id
    LEFT JOIN kadrix_stations s ON i.station_id = s.id
    WHERE 1=1
    """
    params = []
    if line_id:
        sql += " AND i.line_id = %s"
        params.append(line_id)
    if status:
        sql += " AND i.status = %s"
        params.append(status)
    sql += " ORDER BY i.priority DESC, i.expected_savings_usd_annual DESC"
    return query(sql, tuple(params))


def _budget_summary():
    total_budget = 15000.00
    rows = query("""
        SELECT 
            SUM(investment_usd) AS total_invested,
            SUM(implementation_cost_usd) AS total_impl,
            SUM(expected_savings_usd_annual) AS total_savings,
            COUNT(*) AS total_projects
        FROM kadrix_improvements
    """)
    r = rows[0] if rows else {}
    invested = float(r.get("total_invested") or 0)
    impl = float(r.get("total_impl") or 0)
    savings = float(r.get("total_savings") or 0)
    return {
        "total_budget": total_budget,
        "total_invested": invested,
        "total_impl": impl,
        "total_spent": invested + impl,
        "remaining_budget": total_budget - invested - impl,
        "total_savings_annual": savings,
        "roi_pct": round((savings / (invested + impl) * 100), 1) if (invested + impl) > 0 else 0,
        "payback_months": round(((invested + impl) / savings * 12), 1) if savings > 0 else 0,
        "total_projects": r.get("total_projects", 0),
    }


def _line_summary(line_id: int) -> dict:
    baseline = _baseline(line_id)
    improvements = _improvements(line_id)
    total_ct = sum(float(b.get("value") or 0) for b in baseline)
    takt = query("SELECT takt_seconds FROM kadrix_lines WHERE id = %s", (line_id,))
    takt_sec = float(takt[0]["takt_seconds"]) if takt else 2821
    bottleneck = max(baseline, key=lambda x: float(x.get("value") or 0)) if baseline else None
    potential_savings = sum(
        float(i.get("expected_time_saved_sec") or 0) for i in improvements
    )
    return {
        "total_ct": total_ct,
        "takt_sec": takt_sec,
        "gap_sec": total_ct - takt_sec if total_ct > takt_sec else 0,
        "bottleneck_station": bottleneck["station_name"] if bottleneck else None,
        "bottleneck_ct": float(bottleneck["value"]) if bottleneck else 0,
        "improvement_count": len(improvements),
        "potential_time_savings_sec": potential_savings,
        "new_ct_projected": max(total_ct - potential_savings, takt_sec),
    }


# ──────────────────────────────────────────────
#  Analytics Dashboard
# ──────────────────────────────────────────────
@kadrix_bp.route("/analytics")
def analytics():
    lines = _lines()
    improvements = _improvements()
    budget = _budget_summary()
    baseline = _baseline()

    line_summaries = []
    for line in lines:
        line_summaries.append({
            "line": line,
            "summary": _line_summary(line["id"]),
        })

    # Top improvements by ROI
    top_improvements = sorted(
        improvements,
        key=lambda x: float(x.get("expected_savings_usd_annual") or 0),
        reverse=True,
    )[:5]

    return render_template(
        "kadrix/analytics.html",
        title="Cadrex — Analitica & Justificacion ROI",
        nav_active="cadrex",
        lines=lines,
        line_summaries=line_summaries,
        improvements=improvements,
        budget=budget,
        baseline=baseline,
        top_improvements=top_improvements,
    )


# ──────────────────────────────────────────────
#  API endpoints for charts
# ──────────────────────────────────────────────
@kadrix_bp.route("/api/analytics/budget")
def api_budget():
    return jsonify(_budget_summary())


@kadrix_bp.route("/api/analytics/line/<int:line_id>")
def api_line_summary(line_id: int):
    return jsonify(_line_summary(line_id))


@kadrix_bp.route("/api/analytics/improvements")
def api_improvements():
    return jsonify(_improvements())
