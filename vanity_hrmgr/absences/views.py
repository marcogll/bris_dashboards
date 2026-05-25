"""ViewSets para la API REST de inasistencias."""

from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Absence
from .serializers import AbsenceSerializer


class AbsenceViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD para inasistencias.

    Filtra por rol:
    - Admin: ve todas las ausencias
    - Manager: ve ausencias de sus sucursales
    - User: ve solo sus propias ausencias
    """
    serializer_class = AbsenceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role == 'admin':
            return Absence.objects.all()
        elif user.role == 'manager':
            return Absence.objects.filter(sucursal__in=user.branch_set.all())
        return Absence.objects.filter(empleado__user=user)

    def perform_create(self, serializer):
        serializer.save(registrado_por=self.request.user)

    @action(detail=False, methods=['get'])
    def por_empleado(self, request):
        empleado_id = request.query_params.get('empleado_id')
        if not empleado_id:
            return Response({'error': 'Se requiere empleado_id'}, status=status.HTTP_400_BAD_REQUEST)
        absences = self.get_queryset().filter(empleado_id=empleado_id)
        serializer = self.get_serializer(absences, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def por_sucursal(self, request):
        sucursal_id = request.query_params.get('sucursal_id')
        if not sucursal_id:
            return Response({'error': 'Se requiere sucursal_id'}, status=status.HTTP_400_BAD_REQUEST)
        absences = self.get_queryset().filter(sucursal_id=sucursal_id)
        serializer = self.get_serializer(absences, many=True)
        return Response(serializer.data)