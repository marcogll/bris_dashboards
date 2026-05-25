"""Administración de empleados, sucursales y auditoría."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User, Branch, Employee, EmployeeAudit


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "email", "role", "is_active")
    list_filter = ("is_active", "role")
    fieldsets = BaseUserAdmin.fieldsets + ((None, {"fields": ("role", "telegram_chat_id")}),)


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ("name", "address", "active")
    list_filter = ("active",)
    search_fields = ("name",)


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ("__str__", "branch", "status", "employee_number")
    list_filter = ("status", "branch")
    search_fields = ("user__username", "user__first_name", "user__last_name", "employee_number")
    readonly_fields = ("created_at", "updated_at")


@admin.register(EmployeeAudit)
class EmployeeAuditAdmin(admin.ModelAdmin):
    list_display = ("employee", "action", "changed_by", "created_at")
    list_filter = ("action",)
    readonly_fields = ("created_at",)
