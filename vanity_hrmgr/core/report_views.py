"""Vistas para reportes y auditoría del sistema."""

from datetime import date, timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import render

from absences.models import Absence, AbsenceAudit
from employees.models import EmployeeAudit
from hr_requests.models import Request

ACTION_CHOICES = [
    ("create", "Creación"),
    ("update", "Actualización"),
    ("delete", "Eliminación"),
    ("login", "Inicio de sesión"),
    ("logout", "Cierre de sesión"),
]


@login_required
def auditoria_view(request):
    action_filter = request.GET.get("action", "")
    fecha_inicio = request.GET.get("fecha_inicio", "")
    fecha_fin = request.GET.get("fecha_fin", "")

    employee_audits = EmployeeAudit.objects.select_related("employee", "changed_by").all()
    absence_audits = AbsenceAudit.objects.select_related("absence", "changed_by").all()

    if action_filter:
        employee_audits = employee_audits.filter(action=action_filter)
        absence_audits = absence_audits.filter(action=action_filter)

    all_audits = sorted(
        list(employee_audits) + list(absence_audits),
        key=lambda x: x.created_at if hasattr(x, "created_at") and x.created_at else date.min,
        reverse=True,
    )

    context = {
        "audits": all_audits,
        "action_filter": action_filter,
        "fecha_inicio": fecha_inicio,
        "fecha_fin": fecha_fin,
        "action_choices": ACTION_CHOICES,
    }
    return render(request, "core/auditoria.html", context)


@login_required
def metricas_view(request):
    today = date.today()
    months = []
    for i in range(6):
        month_date = today - timedelta(days=30 * i)
        months.append(month_date.strftime("%Y-%m"))

    requests_by_month = []
    absences_by_month = []
    for i in range(6):
        month_date = today - timedelta(days=30 * i)
        month_start = month_date.replace(day=1)
        month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        requests_by_month.append(
            Request.objects.filter(created_at__date__gte=month_start, created_at__date__lte=month_end).count()
        )
        absences_by_month.append(
            Absence.objects.filter(fecha__gte=month_start, fecha__lte=month_end).count()
        )

    ausencias_por_tipo = list(
        Absence.objects.values("tipo").annotate(count=Count("id")).order_by("-count")
    )
    solicitudes_estatus = list(
        Request.objects.values("estatus").annotate(count=Count("id")).order_by("-count")
    )
    total = Request.objects.count()
    tasa_aprobacion = Request.objects.filter(estatus="aprobado").count() / total * 100 if total else 0
    tasa_rechazo = Request.objects.filter(estatus="rechazado").count() / total * 100 if total else 0

    context = {
        "months": list(reversed(months)),
        "requests_by_month": list(reversed(requests_by_month)),
        "absences_by_month": list(reversed(absences_by_month)),
        "ausencias_por_tipo": ausencias_por_tipo,
        "solicitudes_estatus": solicitudes_estatus,
        "tasa_aprobacion": round(tasa_aprobacion, 1),
        "tasa_rechazo": round(tasa_rechazo, 1),
    }
    return render(request, "core/metricas.html", context)
