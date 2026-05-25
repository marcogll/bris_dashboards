"""Serializers para la API REST de solicitudes con validaciones de negocio."""

from rest_framework import serializers
from datetime import date, timedelta

from .models import Request, RequestComment
from employees.models import Employee
from holidays.models import Holiday


class RequestSerializer(serializers.ModelSerializer):
    """Serializer para solicitudes de vacaciones y permisos.

    Valida:
    - Fechas coherentes (inicio <= fin)
    - Saldo suficiente para vacaciones
    - Máximo 3 días hábiles para permisos
    - Anticipación mínima de 24h para permisos
    - Bandera fuera_de_condiciones permite saltar validaciones
    """
    empleado_nombre = serializers.CharField(source='empleado.user.get_full_name', read_only=True)
    dias_solicitados = serializers.IntegerField(read_only=True)
    saldo_vacaciones = serializers.FloatField(source='empleado.saldo_vacaciones', read_only=True)

    class Meta:
        model = Request
        fields = ['id', 'tipo', 'fecha_inicio', 'fecha_fin', 'estatus', 'observaciones_sistema', 'comentario_admin', 'empleado', 'empleado_nombre', 'dias_solicitados', 'fuera_de_condiciones', 'saldo_vacaciones', 'created_at', 'updated_at']
        read_only_fields = ['estatus', 'observaciones_sistema', 'comentario_admin', 'created_at', 'updated_at']

    def validate(self, data):
        if data['fecha_inicio'] > data['fecha_fin']:
            raise serializers.ValidationError('La fecha de inicio no puede ser posterior a la fecha fin')

        empleado = data['empleado']

        if not self._validar_traslapes(empleado, data['fecha_inicio'], data['fecha_fin']):
            raise serializers.ValidationError('Ya existe una solicitud que se traslapa con las fechas seleccionadas')

        if data['tipo'] == 'vacacion':
            dias = self._calcular_dias_habiles(data['fecha_inicio'], data['fecha_fin'])
            if not self.instance:
                if dias > empleado.saldo_vacaciones and not data.get('fuera_de_condiciones', False):
                    raise serializers.ValidationError(f'No tienes saldo suficiente. Saldo actual: {empleado.saldo_vacaciones}, días solicitados: {dias}')
            else:
                dias_actuales = self.instance.dias_solicitados()
                nuevo_saldo = empleado.saldo_vacaciones + dias_actuales
                if dias > nuevo_saldo and not data.get('fuera_de_condiciones', False):
                    raise serializers.ValidationError('Saldo insuficiente')

        if data['tipo'] == 'permiso':
            dias = self._calcular_dias_habiles(data['fecha_inicio'], data['fecha_fin'])
            if dias > 3:
                raise serializers.ValidationError('Los permisos tienen máximo 3 días hábiles')
            anticipacion = data['fecha_inicio'] - date.today()
            if anticipacion.days < 1 and not data.get('fuera_de_condiciones', False):
                raise serializers.ValidationError('Los permisos deben solicitarse con al menos 24 horas de anticipación')

        return data

    def _validar_traslapes(self, empleado, fecha_inicio, fecha_fin):
        queryset = Request.objects.filter(empleado=empleado, estatus__in=['pendiente', 'aprobado'])
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        traslapes = queryset.filter(fecha_inicio__lte=fecha_fin, fecha_fin__gte=fecha_inicio)
        return not traslapes.exists()

    def _calcular_dias_habiles(self, fecha_inicio, fecha_fin):
        dias = 0
        actual = fecha_inicio
        while actual <= fecha_fin:
            if actual.weekday() < 5 and not Holiday.es_dia_festivo(actual):
                dias += 1
            actual += timedelta(days=1)
        return dias


class RequestCommentSerializer(serializers.ModelSerializer):
    """Serializer para comentarios en solicitudes."""
    author_nombre = serializers.CharField(source='author.get_full_name', read_only=True)

    class Meta:
        model = RequestComment
        fields = ['id', 'request', 'author', 'author_nombre', 'contenido', 'created_at']
        read_only_fields = ['author', 'created_at']