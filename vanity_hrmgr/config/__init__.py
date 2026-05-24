"""Inicializa Celery cuando se carga el proyecto Django."""

from celery import app as celery_app

__all__ = ('celery_app',)