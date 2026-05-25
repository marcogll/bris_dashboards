"""Modelos de catálogo: configuraciones globales y logs de notificaciones."""

from django.db import models


class Configuration(models.Model):
    key = models.CharField(max_length=100, unique=True)
    value = models.TextField(blank=True, default="")
    description = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuración"
        verbose_name_plural = "Configuraciones"

    def __str__(self):
        return self.key


class NotificationLog(models.Model):
    TYPE_CHOICES = [
        ("telegram", "Telegram"),
        ("email", "Email"),
        ("sms", "SMS"),
    ]
    STATUS_CHOICES = [
        ("pending", "Pendiente"),
        ("sent", "Enviado"),
        ("failed", "Fallido"),
    ]
    tipo = models.CharField(max_length=20, choices=TYPE_CHOICES)
    destinatario = models.CharField(max_length=255)
    mensaje = models.TextField()
    estatus = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    error_message = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Log de Notificación"
        verbose_name_plural = "Logs de Notificaciones"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.tipo} - {self.destinatario} - {self.estatus}"
