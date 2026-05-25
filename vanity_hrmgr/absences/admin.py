"""Administración del módulo inasistencias: registros y auditoría."""

from django.contrib import admin
from .models import Absence, AbsenceAudit


@admin.register(Absence)
class AbsenceAdmin(admin.ModelAdmin):
    """Panel de administración para registro de inasistencias."""
    list_display = ('empleado', 'fecha', 'sucursal', 'tipo', 'registrado_por', 'created_at')
    list_filter = ('tipo', 'fecha', 'sucursal')
    search_fields = ('empleado__user__first_name', 'empleado__user__last_name', 'empleado__employee_number')
    readonly_fields = ('created_at',)


@admin.register(AbsenceAudit)
class AbsenceAuditAdmin(admin.ModelAdmin):
    """Panel de auditoría para cambios en registros de inasistencias."""
    list_display = ('absence', 'action', 'changed_by', 'created_at')
    list_filter = ('action',)
    readonly_fields = ('created_at',)