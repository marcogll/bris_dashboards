"""Serializers para la API REST de inasistencias."""

from rest_framework import serializers
from .models import Absence
from datetime import date


class AbsenceSerializer(serializers.ModelSerializer):
    """Serializer para registro de inasistencias.

    Valida que no se puedan registrar ausencias con fechas futuras.
    """
    empleado_nombre = serializers.CharField(source='empleado.user.get_full_name', read_only=True)
    sucursal_nombre = serializers.CharField(source='sucursal.name', read_only=True)
    registrado_por_nombre = serializers.CharField(source='registrado_por.get_full_name', read_only=True)

    class Meta:
        model = Absence
        fields = ('id', 'empleado', 'empleado_nombre', 'fecha', 'sucursal', 'sucursal_nombre', 'tipo', 'motivo', 'registrado_por', 'registrado_por_nombre', 'created_at')
        read_only_fields = ('registrado_por', 'created_at')

    def validate(self, data):
        if data['fecha'] > date.today():
            raise serializers.ValidationError('No se pueden registrar ausencias futuras')
        return data