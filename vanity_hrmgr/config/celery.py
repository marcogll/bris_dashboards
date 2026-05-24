"""Configuración de Celery para tareas asíncronas del sistema.

Este módulo inicializa Celery con Django para procesamiento de tareas
asíncronas como notificaciones de Telegram y actualizaciones de saldo.
"""

import os

from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('config')

app.config_from_object('django.conf:settings', namespace='CELERY')

app.autodiscover_tasks()


@app.task(bind=True)
def debug_task(self):
    return f'Request: {self.request.id!r}'