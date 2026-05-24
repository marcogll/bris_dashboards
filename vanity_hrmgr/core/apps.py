"""App central para configuraciones globales y logs de notificaciones."""

from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
    verbose_name = 'Catálogos y Configuración'