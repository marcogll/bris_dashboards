"""Configuración de la app empleados: usuarios, sucursales y perfiles."""

from django.apps import AppConfig


class EmployeesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'employees'
    verbose_name = 'Empleados y Sucursales'

    def ready(self):
        import employees.signals  # noqa: F401