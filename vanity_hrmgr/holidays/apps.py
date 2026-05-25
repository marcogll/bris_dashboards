"""Configuración de la app feriados: días festivos mexicanos."""

from django.apps import AppConfig


class HolidaysConfig(AppConfig):
    """App para gestión de días festivos del calendario laboral mexicano."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'holidays'
    verbose_name = 'Feriados'