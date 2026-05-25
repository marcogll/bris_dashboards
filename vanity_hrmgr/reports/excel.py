from io import BytesIO

from django.http import HttpResponse
from openpyxl import Workbook


def _vacaciones_row(r):
    return [
        r.id,
        str(r.empleado),
        r.get_tipo_display(),
        r.fecha_inicio.isoformat() if r.fecha_inicio else "",
        r.fecha_fin.isoformat() if r.fecha_fin else "",
        r.get_estatus_display(),
        "Sí" if r.fuera_de_condiciones else "No",
        r.comentario_admin or "",
        r.created_at.isoformat() if r.created_at else "",
    ]


def _ausencias_row(r):
    return [
        r.id,
        str(r.empleado),
        str(r.sucursal) if r.sucursal else "",
        r.get_tipo_display(),
        r.fecha.isoformat() if r.fecha else "",
        r.motivo or "",
        str(r.registrado_por) if r.registrado_por else "",
        r.created_at.isoformat() if r.created_at else "",
    ]


def generate_excel_report(request, report_type):
    if report_type in ("vacaciones", "permisos"):
        from hr_requests.models import Request

        qs = Request.objects.select_related("empleado", "empleado__user")
        if report_type == "vacaciones":
            qs = qs.filter(tipo="vacacion")
            filename = "reporte_vacaciones.xlsx"
            title = "Reporte de Vacaciones"
        else:
            qs = qs.filter(tipo="permiso")
            filename = "reporte_permisos.xlsx"
            title = "Reporte de Permisos"
        headers = [
            "ID",
            "Empleado",
            "Tipo",
            "Fecha Inicio",
            "Fecha Fin",
            "Estatus",
            "Fuera de Condiciones",
            "Comentario Admin",
            "Fecha Creación",
        ]
        row_fn = _vacaciones_row
    elif report_type == "ausencias":
        from absences.models import Absence

        qs = Absence.objects.select_related("empleado", "empleado__user")
        filename = "reporte_ausencias.xlsx"
        title = "Reporte de Ausencias"
        headers = [
            "ID",
            "Empleado",
            "Sucursal",
            "Tipo",
            "Fecha",
            "Motivo",
            "Registrado Por",
            "Fecha Creación",
        ]
        row_fn = _ausencias_row
    else:
        return HttpResponse(f"Reporte desconocido: {report_type}", status=400)

    wb = Workbook()
    ws = wb.active
    ws.title = title[:31]

    ws.append(headers)
    for obj in qs.order_by("-created_at"):
        ws.append(row_fn(obj))

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)

    resp = HttpResponse(
        buf.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    resp["Content-Disposition"] = f"attachment; filename={filename}"
    return resp