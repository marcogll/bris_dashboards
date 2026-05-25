"""Configuración de la app solicitudes: vacaciones y permisos."""

from django.apps import AppConfig


class RequestsConfig(AppConfig):
    """App para gestión de solicitudes de vacaciones y permisos."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'hr_requests'
    verbose_name = 'Solicitudes'

    def ready(self):
        import hr_requests.signals