"""Modelos para solicitudes de vacaciones y permisos."""

from django.db import models
from employees.models import Employee


class Request(models.Model):
    """Solicitud de vacaciones o permiso de un empleado."""
    TYPE_CHOICES = [
        ('vacacion', 'Vacación'),
        ('permiso', 'Permiso'),
    ]
    STATUS_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('aprobado', 'Aprobado'),
        ('rechazado', 'Rechazado'),
    ]
    tipo = models.CharField(max_length=20, choices=TYPE_CHOICES)
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    estatus = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pendiente')
    observaciones_sistema = models.TextField(blank=True)
    comentario_admin = models.TextField(blank=True)
    empleado = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='requests')
    fuera_de_condiciones = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'requests'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.tipo} - {self.empleado} ({self.estatus})'

    def dias_solicitados(self):
        from datetime import date, timedelta
        from holidays.models import Holiday
        dias = 0
        actual = self.fecha_inicio
        while actual <= self.fecha_fin:
            if actual.weekday() < 5:
                if not Holiday.es_dia_festivo(actual):
                    dias += 1
            actual += timedelta(days=1)
        return dias


class RequestComment(models.Model):
    """Comentario en el historial de una solicitud."""
    request = models.ForeignKey(Request, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey('employees.User', on_delete=models.SET_NULL, null=True)
    contenido = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'request_comments'
        ordering = ['created_at']