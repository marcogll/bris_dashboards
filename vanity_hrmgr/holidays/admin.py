"""Administración del módulo feriados: días festivos mexicanos."""

from django.contrib import admin
from .models import Holiday


@admin.register(Holiday)
class HolidayAdmin(admin.ModelAdmin):
    """Panel de administración para días festivos del calendario laboral."""
    list_display = ('fecha', 'descripcion', 'activo')
    list_filter = ('activo',)
    search_fields = ('descripcion',)
    ordering = ('fecha',)