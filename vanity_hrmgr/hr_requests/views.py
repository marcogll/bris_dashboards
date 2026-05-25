"""ViewSets para la API REST de solicitudes con permisos por rol.

Integra notificaciones asíncronas vía Celery cuando se crea una solicitud.
"""

from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Request, RequestComment
from .serializers import RequestSerializer, RequestCommentSerializer


class IsAdminOrReadOnly(permissions.BasePermission):
    """Permite lectura a todos los autenticados, escritura solo a admin/manager."""
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user.is_authenticated and request.user.role in ('admin', 'manager')

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        if request.user.role == 'admin':
            return True
        if request.user.role == 'manager':
            return obj.empleado.branch in request.user.branch_set.all()
        return obj.empleado.user == request.user


class IsOwnerOrAdmin(permissions.BasePermission):
    """Permite acceso solo al dueño de la solicitud o administradores."""
    def has_object_permission(self, request, view, obj):
        if request.user.role == 'admin':
            return True
        if request.user.role == 'manager':
            return obj.empleado.branch in request.user.branch_set.all()
        return obj.usuario == request.user


class RequestViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD para solicitudes de vacaciones y permisos.

    Acciones especiales:
    - aprobar: Cambia estatus a aprobado y descuenta saldo de vacaciones
    - rechazar: Cambia estatus a rechazado con comentario
    """
    serializer_class = RequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role == 'admin':
            return Request.objects.all()
        if user.role == 'manager':
            branches = user.branch_set.all()
            return Request.objects.filter(empleado__branch__in=branches)
        return Request.objects.filter(empleado__user=user)

    def perform_create(self, serializer):
        empleado = self.request.user.employee
        request_obj = serializer.save(empleado=empleado)
        try:
            from telegram_bot.tasks import enviar_notificacion_admin
            enviar_notificacion_admin.delay(request_obj.id)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f'Error enviando notificación: {e}')

    @action(detail=True, methods=['post'])
    def aprobar(self, request, pk=None):
        request_obj = self.get_object()
        if request_obj.estatus != 'pendiente':
            return Response({'error': 'La solicitud ya fue procesada'}, status=status.HTTP_400_BAD_REQUEST)
        request_obj.estatus = 'aprobado'
        request_obj.comentario_admin = request.data.get('comentario', '')
        request_obj.save()
        if request_obj.tipo == 'vacacion':
            dias = request_obj.dias_solicitados()
            empleado = request_obj.empleado
            empleado.saldo_vacaciones -= dias
            empleado.save()
        return Response(RequestSerializer(request_obj).data)

    @action(detail=True, methods=['post'])
    def rechazar(self, request, pk=None):
        request_obj = self.get_object()
        if request_obj.estatus != 'pendiente':
            return Response({'error': 'La solicitud ya fue procesada'}, status=status.HTTP_400_BAD_REQUEST)
        request_obj.estatus = 'rechazado'
        request_obj.comentario_admin = request.data.get('comentario', '')
        request_obj.save()
        return Response(RequestSerializer(request_obj).data)


class RequestCommentViewSet(viewsets.ModelViewSet):
    """ViewSet para comentarios en solicitudes. Solo crea y lista."""
    serializer_class = RequestCommentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return RequestComment.objects.filter(request_id=self.kwargs['request_pk'])

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)