"""Serializers para la API REST de empleados."""

from rest_framework import serializers

from .models import User, Branch, Employee


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="get_full_name", read_only=True)

    class Meta:
        model = User
        fields = ["id", "username", "email", "full_name", "role", "is_active"]


class BranchSerializer(serializers.ModelSerializer):
    empleados_count = serializers.SerializerMethodField()

    class Meta:
        model = Branch
        fields = ["id", "nombre", "direccion", "empleados_count"]

    def get_empleados_count(self, obj):
        return obj.employee_set.count() if hasattr(obj, "employee_set") else 0


class EmployeePublicSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    branch_nombre = serializers.CharField(source="branch.nombre", read_only=True)

    class Meta:
        model = Employee
        fields = ["id", "user", "branch_nombre", "puesto", "nivel_habilidad", "estatus"]


class EmployeeSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    branch_nombre = serializers.CharField(source="branch.nombre", read_only=True)

    class Meta:
        model = Employee
        fields = [
            "id",
            "user",
            "branch",
            "branch_nombre",
            "puesto",
            "telefono",
            "nivel_habilidad",
            "calificacion",
            "activo",
            "estatus",
        ]


class EmployeeCreateSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(write_only=True)
    password = serializers.CharField(write_only=True)

    class Meta:
        model = Employee
        fields = ["email", "password", "branch", "puesto", "telefono"]
