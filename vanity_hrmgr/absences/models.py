"""Modelos para registro de inasistencias y su auditoría."""

from django.db import models
from employees.models import Employee, Branch, User


class Absence(models.Model):
    """Registro de una inasistencia o incidencia laboral."""

    TYPE_CHOICES = [
        ('injustificada', 'Injustificada'),
        ('enfermedad', 'Enfermedad'),
        ('suspension', 'Suspensión'),
        ('retardo', 'Retardo'),
        ('permiso_sin_goce', 'Permiso sin goce'),
        ('otro', 'Otro'),
    ]

    empleado = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='absences')
    fecha = models.DateField()
    sucursal = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True)
    tipo = models.CharField(max_length=30, choices=TYPE_CHOICES)
    motivo = models.TextField(blank=True)
    registrado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'absences'
        ordering = ['-fecha', '-created_at']

    def __str__(self):
        return f'{self.empleado} - {self.fecha} ({self.tipo})'


class AbsenceAudit(models.Model):
    """Registro de auditoría para cambios en inasistencias."""

    ACTION_CHOICES = [
        ('create', 'Creado'),
        ('update', 'Actualizado'),
        ('delete', 'Eliminado'),
    ]

    absence = models.ForeignKey(Absence, on_delete=models.CASCADE, related_name='audits')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    field_changed = models.CharField(max_length=50, blank=True)
    old_value = models.TextField(blank=True)
    new_value = models.TextField(blank=True)
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'absence_audits'
        ordering = ['-created_at']