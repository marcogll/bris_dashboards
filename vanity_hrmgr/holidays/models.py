"""Modelos y utilidades para gestión de días festivos mexicanos."""

from django.db import models
from datetime import date


class Holiday(models.Model):
    """Representa un día festivo en el calendario laboral."""
    fecha = models.DateField(unique=True)
    descripcion = models.CharField(max_length=200)
    activo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'holidays'
        ordering = ['fecha']

    def __str__(self):
        return f'{self.fecha} - {self.descripcion}'

    @classmethod
    def es_dia_festivo(cls, fecha) -> bool:
        """Verifica si una fecha es día festivo activo.

        Args:
            fecha: Fecha a verificar

        Returns:
            True si la fecha es festivo activo, False en caso contrario
        """
        return cls.objects.filter(fecha=fecha, activo=True).exists()

    @classmethod
    def dias_habiles(cls, fecha_inicio: date, fecha_fin: date) -> int:
        """Calcula días hábiles entre dos fechas excluyendo festivos.

        Args:
            fecha_inicio: Fecha de inicio (inclusive)
            fecha_fin: Fecha de fin (inclusive)

        Returns:
            Número de días hábiles
        """
        dias = 0
        actual = fecha_inicio
        while actual <= fecha_fin:
            if actual.weekday() < 5 and not cls.es_dia_festivo(actual):
                dias += 1
            if actual.day < 28:
                actual = date(actual.year, actual.month, actual.day + 1)
            else:
                next_month = actual.month + 1 if actual.month < 12 else 1
                actual = date(actual.year, next_month, 1)
        return dias