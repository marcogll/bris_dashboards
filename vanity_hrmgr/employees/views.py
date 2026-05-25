"""ViewSets para la API REST de empleados y sucursales."""

from datetime import date

from django.db import transaction
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import User, Branch, Employee
from .serializers import (
    UserSerializer,
    BranchSerializer,
    EmployeeSerializer,
    EmployeeCreateSerializer,
    EmployeePublicSerializer,
)


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer


class BranchViewSet(viewsets.ModelViewSet):
    queryset = Branch.objects.all()
    serializer_class = BranchSerializer


def _parse_stars(star_str):
    if isinstance(star_str, (int, float)):
        return int(star_str)
    count = 0
    for ch in str(star_str):
        if ch in ("★", "*"):
            count += 1
    return count


_SKILL_LEVEL_MAP = {
    "principiante": 1,
    "básico": 1,
    "basico": 1,
    "intermedio": 2,
    "avanzado": 3,
    "experto": 4,
}


def _parse_skill_level(skill_str):
    return _SKILL_LEVEL_MAP.get(str(skill_str).lower().strip(), 1)


_STATUS_MAP = {
    "activa": True,
    "activo": True,
    "inactiva": False,
    "inactivo": False,
    "baja": False,
}


def _parse_status(status_str):
    return _STATUS_MAP.get(str(status_str).lower().strip(), True)


class EmployeeViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Employee.objects.select_related("user", "branch").all()

    def get_serializer_class(self):
        if self.action == "create":
            return EmployeeCreateSerializer
        return EmployeeSerializer

    @action(detail=False, methods=["get"])
    def public(self, request):
        employees = Employee.objects.select_related("user", "branch").filter(user__is_active=True)
        serializer = EmployeePublicSerializer(employees, many=True)
        return Response(serializer.data)
