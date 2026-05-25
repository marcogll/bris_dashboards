"""Configuración de la app inasistencias: faltas e incidencias."""

from django.apps import AppConfig


class AbsencesConfig(AppConfig):
    """App para registro y auditoría de inasistencias laborales."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'absences'
    verbose_name = 'Inasistencias'