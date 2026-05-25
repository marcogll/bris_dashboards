"""Vistas API adicionales para dashboard y métricas."""

from datetime import date, timedelta

from django.db.models import Count, Q
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from absences.models import Absence
from employees.models import Branch, Employee
from hr_requests.models import Request


class DashboardAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        today = date.today()
        pending = Request.objects.filter(estatus="pendiente").count()
        approved = Request.objects.filter(estatus="aprobado").count()
        rejected = Request.objects.filter(estatus="rechazado").count()
        absences_today = Absence.objects.filter(fecha=today).count()
        employees_active = Employee.objects.filter(activo=True).count()

        return Response(
            {
                "pending_requests": pending,
                "approved_requests": approved,
                "rejected_requests": rejected,
                "absences_today": absences_today,
                "active_employees": employees_active,
            }
        )


class CalendarEventsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        start_date = request.query_params.get("start", None)
        end_date = request.query_params.get("end", None)
        events = []

        qs = Request.objects.all()
        if start_date:
            qs = qs.filter(fecha_inicio__gte=start_date)
        if end_date:
            qs = qs.filter(fecha_fin__lte=end_date)

        for r in qs.select_related("empleado"):
            events.append(
                {
                    "id": r.id,
                    "title": f"{r.empleado} - {r.get_tipo_display()}",
                    "start": r.fecha_inicio.isoformat() if r.fecha_inicio else None,
                    "end": r.fecha_fin.isoformat() if r.fecha_fin else None,
                    "tipo": r.tipo,
                    "estatus": r.estatus,
                }
            )

        abs_qs = Absence.objects.all()
        if start_date:
            abs_qs = abs_qs.filter(fecha__gte=start_date)
        if end_date:
            abs_qs = abs_qs.filter(fecha__lte=end_date)

        for a in abs_qs.select_related("empleado"):
            events.append(
                {
                    "id": f"abs-{a.id}",
                    "title": f"{a.empleado} - Ausencia",
                    "start": a.fecha.isoformat() if a.fecha else None,
                    "tipo": "ausencia",
                    "estatus": "confirmada",
                }
            )

        return Response(events)
