"""Cadrex — Flask views/routes."""
from datetime import date, datetime, timedelta

from flask import (
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from . import kadrix_bp
from .db import execute, query


# ──────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────
def _ensure_default_board():
    """Create default Kanban board + columns if none exist."""
    boards = query("SELECT id FROM kadrix_boards LIMIT 1")
    if boards:
        return boards[0]["id"]
    bid = execute(
        "INSERT INTO kadrix_boards (name, description) VALUES (%s, %s)",
        ("Produccion y Mantenimiento", "Tablero principal de tareas Cadrex"),
    )
    if not bid:
        return 1  # fallback cuando DB no está disponible
    cols = [
        ("Backlog", 0, "#64748b"),
        ("In Progress", 1, "#2563eb"),
        ("Testing", 2, "#d97706"),
        ("Done", 3, "#16a34a"),
    ]
    for name, pos, color in cols:
        execute(
            "INSERT INTO kadrix_columns (board_id, name, position, color) VALUES (%s, %s, %s, %s)",
            (bid, name, pos, color),
        )
    return bid


def _board_data(board_id: int) -> dict:
    board = query("SELECT * FROM kadrix_boards WHERE id = %s", (board_id,))
    if not board:
        return {}
    columns = query(
        "SELECT * FROM kadrix_columns WHERE board_id = %s ORDER BY position",
        (board_id,),
    )
    tasks = query(
        """
        SELECT t.*,
               u.name AS assigned_name,
               c.name AS column_name
        FROM kadrix_tasks t
        LEFT JOIN kadrix_users u ON t.assigned_to = u.id
        JOIN kadrix_columns c ON t.column_id = c.id
        WHERE t.board_id = %s
        ORDER BY t.priority DESC, t.due_date ASC
        """,
        (board_id,),
    )
    return {
        "board": board[0],
        "columns": columns,
        "tasks": tasks,
    }


def _fixtures_stats() -> dict:
    rows = query("SELECT COUNT(*) AS n FROM kadrix_fixtures")
    total = rows[0]["n"] if rows else 0
    by_status = query(
        "SELECT status, COUNT(*) AS n FROM kadrix_fixtures GROUP BY status"
    )
    by_line = query(
        "SELECT line, COUNT(*) AS n FROM kadrix_fixtures WHERE line IS NOT NULL GROUP BY line"
    )
    rows_maint = query("SELECT COUNT(*) AS n FROM kadrix_fixtures WHERE status = 'maintenance'")
    in_maintenance = rows_maint[0]["n"] if rows_maint else 0
    rows_dmg = query("SELECT COUNT(*) AS n FROM kadrix_fixtures WHERE status = 'inactive'")
    damaged = rows_dmg[0]["n"] if rows_dmg else 0
    return {
        "total": total,
        "by_status": {r["status"]: r["n"] for r in by_status},
        "by_line": {r["line"]: r["n"] for r in by_line},
        "in_maintenance": in_maintenance,
        "damaged": damaged,
    }


def _projects_stats() -> dict:
    rows = query("SELECT COUNT(*) AS n FROM kadrix_projects")
    total = rows[0]["n"] if rows else 0
    rows_active = query("SELECT COUNT(*) AS n FROM kadrix_projects WHERE status = 'active'")
    active = rows_active[0]["n"] if rows_active else 0
    rows_comp = query("SELECT COUNT(*) AS n FROM kadrix_projects WHERE status = 'completed'")
    completed = rows_comp[0]["n"] if rows_comp else 0
    return {"total": total, "active": active, "completed": completed}


def _overdue_tasks() -> list:
    today = date.today().isoformat()
    return query(
        """
        SELECT t.*, u.name AS assigned_name, c.name AS column_name
        FROM kadrix_tasks t
        LEFT JOIN kadrix_users u ON t.assigned_to = u.id
        JOIN kadrix_columns c ON t.column_id = c.id
        WHERE t.due_date < %s AND c.name != 'Done'
        ORDER BY t.due_date ASC
        LIMIT 20
        """,
        (today,),
    )


# ──────────────────────────────────────────────
#  HQ Dashboard
# ──────────────────────────────────────────────
@kadrix_bp.route("/")
def kadrix_hq():
    bid = _ensure_default_board()
    board_data = _board_data(bid)
    fixture_stats = _fixtures_stats()
    project_stats = _projects_stats()
    overdue = _overdue_tasks()

    # KPI counts
    total_tasks = len(board_data.get("tasks", []))
    active_tasks = len(
        [t for t in board_data.get("tasks", []) if t.get("column_name") != "Done"]
    )
    total_fixtures = fixture_stats.get("total", 0)
    fixtures_ok = total_fixtures - fixture_stats.get("in_maintenance", 0) - fixture_stats.get("damaged", 0)

    return render_template(
        "kadrix/hq.html",
        title="Cadrex — Centro de Control",
        nav_active="cadrex",
        board=board_data.get("board"),
        total_tasks=total_tasks,
        active_tasks=active_tasks,
        total_fixtures=total_fixtures,
        fixtures_ok=fixtures_ok,
        fixtures_maintenance=fixture_stats.get("in_maintenance", 0),
        fixtures_damaged=fixture_stats.get("damaged", 0),
        project_active=project_stats.get("active", 0),
        project_total=project_stats.get("total", 0),
        overdue=overdue,
    )


# ──────────────────────────────────────────────
#  Kanban Board
# ──────────────────────────────────────────────
@kadrix_bp.route("/board/<int:board_id>")
def kadrix_board(board_id: int):
    data = _board_data(board_id)
    if not data:
        return "Board not found", 404
    users = query("SELECT id, name FROM kadrix_users WHERE active = 1")
    return render_template(
        "kadrix/board.html",
        title=f"Cadrex — {data['board']['name']}",
        nav_active="cadrex",
        board=data["board"],
        columns=data["columns"],
        tasks=data["tasks"],
        users=users,
    )


@kadrix_bp.route("/board/<int:board_id>/task/create", methods=["POST"])
def create_task(board_id: int):
    title = request.form.get("title", "").strip()
    column_id = request.form.get("column_id", type=int)
    assigned_to = request.form.get("assigned_to", type=int) or None
    priority = request.form.get("priority", "medium")
    due_date = request.form.get("due_date") or None
    description = request.form.get("description", "").strip()
    if not title or not column_id:
        return jsonify({"ok": False, "error": "Title and column required"}), 400

    tid = execute(
        """
        INSERT INTO kadrix_tasks
        (board_id, column_id, title, description, assigned_to, priority, due_date, created_by)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (board_id, column_id, title, description, assigned_to, priority, due_date, None),
    )
    return jsonify({"ok": True, "task_id": tid})


@kadrix_bp.route("/task/<int:task_id>/move", methods=["POST"])
def move_task(task_id: int):
    column_id = request.json.get("column_id", type=int) if request.is_json else None
    if not column_id:
        return jsonify({"ok": False, "error": "column_id required"}), 400
    execute(
        "UPDATE kadrix_tasks SET column_id = %s WHERE id = %s",
        (column_id, task_id),
    )
    return jsonify({"ok": True, "task_id": task_id, "column_id": column_id})


# ──────────────────────────────────────────────
#  Fixtures
# ──────────────────────────────────────────────
@kadrix_bp.route("/fixtures")
def kadrix_fixtures():
    line_filter = request.args.get("line", "").strip()
    status_filter = request.args.get("status", "").strip()
    sql = "SELECT * FROM kadrix_fixtures WHERE 1=1"
    params = []
    if line_filter:
        sql += " AND line = %s"
        params.append(line_filter)
    if status_filter:
        sql += " AND status = %s"
        params.append(status_filter)
    sql += " ORDER BY code"
    fixtures = query(sql, tuple(params))
    lines = [r["line"] for r in query("SELECT DISTINCT line FROM kadrix_fixtures WHERE line IS NOT NULL")]
    stats = _fixtures_stats()
    return render_template(
        "kadrix/fixtures.html",
        title="Cadrex — Catalogo de Fixtures",
        nav_active="cadrex",
        fixtures=fixtures,
        lines=lines,
        stats=stats,
        line_filter=line_filter,
        status_filter=status_filter,
    )


@kadrix_bp.route("/fixtures/create", methods=["POST"])
def create_fixture():
    code = request.form.get("code", "").strip()
    name = request.form.get("name", "").strip()
    line = request.form.get("line", "").strip() or None
    station = request.form.get("station", "").strip() or None
    location = request.form.get("location", "").strip() or None
    notes = request.form.get("notes", "").strip() or None
    if not code or not name:
        return jsonify({"ok": False, "error": "Code and name required"}), 400
    try:
        fid = execute(
            "INSERT INTO kadrix_fixtures (code, name, line, station, location, notes) VALUES (%s, %s, %s, %s, %s, %s)",
            (code, name, line, station, location, notes),
        )
        return jsonify({"ok": True, "fixture_id": fid})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


@kadrix_bp.route("/fixtures/<int:fixture_id>/maintenance", methods=["POST"])
def create_maintenance(fixture_id: int):
    mtype = request.form.get("type", "corrective")
    description = request.form.get("description", "").strip()
    technician = request.form.get("technician", type=int) or None
    downtime = request.form.get("downtime_minutes", type=int) or None
    if not description:
        return jsonify({"ok": False, "error": "Description required"}), 400
    mid = execute(
        """
        INSERT INTO kadrix_fixture_maintenance
        (fixture_id, type, description, technician, downtime_minutes, started_at, status)
        VALUES (%s, %s, %s, %s, %s, NOW(), 'in_progress')
        """,
        (fixture_id, mtype, description, technician, downtime),
    )
    execute(
        "UPDATE kadrix_fixtures SET status = 'maintenance' WHERE id = %s",
        (fixture_id,),
    )
    return jsonify({"ok": True, "maintenance_id": mid})


# ──────────────────────────────────────────────
#  Projects
# ──────────────────────────────────────────────
@kadrix_bp.route("/projects")
def kadrix_projects():
    projects = query("SELECT * FROM kadrix_projects ORDER BY created_at DESC")
    # Simple progress: count tasks linked / total tasks in project
    for p in projects:
        total_linked = query(
            "SELECT COUNT(*) AS n FROM kadrix_project_tasks WHERE project_id = %s",
            (p["id"],),
        )[0]["n"]
        completed_linked = query(
            """
            SELECT COUNT(*) AS n
            FROM kadrix_project_tasks pt
            JOIN kadrix_tasks t ON pt.task_id = t.id
            JOIN kadrix_columns c ON t.column_id = c.id
            WHERE pt.project_id = %s AND c.name = 'Done'
            """,
            (p["id"],),
        )[0]["n"]
        p["progress"] = round(completed_linked / total_linked * 100, 1) if total_linked else 0
    return render_template(
        "kadrix/projects.html",
        title="Cadrex — Proyectos de Mejora",
        nav_active="cadrex",
        projects=projects,
    )


@kadrix_bp.route("/projects/create", methods=["POST"])
def create_project():
    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()
    objective = request.form.get("objective", "").strip()
    budget = request.form.get("budget", type=float) or None
    start_date = request.form.get("start_date") or None
    end_date = request.form.get("end_date") or None
    roi = request.form.get("roi_expected", type=float) or None
    if not name:
        return jsonify({"ok": False, "error": "Name required"}), 400
    pid = execute(
        """
        INSERT INTO kadrix_projects
        (name, description, objective, budget, start_date, end_date, roi_expected)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (name, description, objective, budget, start_date, end_date, roi),
    )
    return jsonify({"ok": True, "project_id": pid})


# ──────────────────────────────────────────────
#  Activities
# ──────────────────────────────────────────────
@kadrix_bp.route("/activity")
def kadrix_activity():
    today = date.today().isoformat()
    week_ago = (date.today() - timedelta(days=7)).isoformat()
    activities = query(
        """
        SELECT a.*, u.name AS user_name
        FROM kadrix_activities a
        JOIN kadrix_users u ON a.user_id = u.id
        WHERE DATE(a.created_at) >= %s
        ORDER BY a.created_at DESC
        LIMIT 100
        """,
        (week_ago,),
    )
    today_activities = [a for a in activities if str(a["created_at"].date()) == today]
    hours_by_type = query(
        """
        SELECT activity_type, SUM(duration_minutes) AS total_min
        FROM kadrix_activities
        WHERE DATE(created_at) >= %s
        GROUP BY activity_type
        """,
        (week_ago,),
    )
    fixtures = query("SELECT id, code, name FROM kadrix_fixtures ORDER BY code")
    return render_template(
        "kadrix/activity.html",
        title="Cadrex — Registro de Actividades",
        nav_active="cadrex",
        activities=activities,
        today_activities=today_activities,
        hours_by_type=hours_by_type,
        fixtures=fixtures,
    )


@kadrix_bp.route("/activity/create", methods=["POST"])
def create_activity():
    atype = request.form.get("activity_type", "other")
    description = request.form.get("description", "").strip()
    fixture_id = request.form.get("fixture_id", type=int) or None
    duration = request.form.get("duration_minutes", type=int) or None
    if not description:
        return jsonify({"ok": False, "error": "Description required"}), 400
    execute(
        """
        INSERT INTO kadrix_activities
        (user_id, activity_type, description, related_fixture_id, duration_minutes)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (1, atype, description, fixture_id, duration),
    )
    return jsonify({"ok": True})
