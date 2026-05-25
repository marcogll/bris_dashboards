"""Vistas web del dashboard para Admin, Manager y Colaborador."""

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta

from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.core.paginator import Paginator
from django.utils.html import escape
from django.http import JsonResponse, HttpResponse
from django.conf import settings

from employees.models import User, Branch, Employee
from hr_requests.models import Request
from hr_requests.forms import RequestForm
from absences.models import Absence, AbsenceAudit
from absences.forms import AbsenceForm
from holidays.models import Holiday
from reports import generate_excel_report
from core.security import rate_limit


PAYROLL_BASE_URL = os.getenv("PAYROLL_BASE_URL", "http://127.0.0.1:5051")
PAYROLL_PUBLIC_URL = os.getenv("PAYROLL_PUBLIC_URL", PAYROLL_BASE_URL)


def _payroll_url(path):
    return f"{PAYROLL_BASE_URL.rstrip('/')}/{path.lstrip('/')}"


def _fetch_json(url, timeout=10):
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


@login_required
def dashboard(request):
    user = request.user
    employees_total = Employee.objects.filter(status='activo').count()
    employees_baja = Employee.objects.filter(status='baja').count()
    branches_total = Branch.objects.filter(active=True).count()
    requests_total = Request.objects.count()
    absences_total = Absence.objects.count()
    holidays_total = Holiday.objects.filter(activo=True).count()
    pending_requests = Request.objects.filter(status='pendiente').count()
    context = {
        'employees_total': employees_total,
        'employees_baja': employees_baja,
        'branches_total': branches_total,
        'requests_total': requests_total,
        'absences_total': absences_total,
        'holidays_total': holidays_total,
        'total_empleados': employees_total,
        'total_sucursales': branches_total,
        'solicitudes_pendientes': pending_requests,
    }
    return render(request, 'dashboard.html', context)


def login_view(request):
    if request.method == 'POST':
        username = escape(request.POST.get('username', ''))
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('dashboard')
        messages.error(request, 'Credenciales incorrectas')
    return render(request, 'login.html')


def logout_view(request):
    logout(request)
    return redirect('login')


@login_required
def empleados_view(request):
    employees = Employee.objects.select_related('user', 'branch').filter(status='activo')
    return render(request, 'empleados.html', {'employees': employees})


@login_required
def solicitudes_view(request):
    solicitudes = Request.objects.select_related('employee', 'employee__user').all()
    return render(request, 'solicitudes.html', {'solicitudes': solicitudes})


@login_required
def solicitudes_pendientes_view(request):
    solicitudes = Request.objects.select_related('employee', 'employee__user').filter(status='pendiente')
    return render(request, 'solicitudes_pendientes.html', {'solicitudes': solicitudes})


@login_required
def ausencias_view(request):
    absences = Absence.objects.select_related('employee', 'employee__user').all()
    return render(request, 'ausencias.html', {'absences': absences})


@login_required
def registrar_ausencia(request):
    if request.method == 'POST':
        form = AbsenceForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Ausencia registrada.')
            return redirect('ausencias')
    else:
        form = AbsenceForm()
    return render(request, 'registrar_ausencia.html', {'form': form})


@login_required
def sucursales_view(request):
    branches = Branch.objects.filter(active=True)
    return render(request, 'sucursales.html', {'branches': branches})


@login_required
def crear_sucursal(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if name:
            Branch.objects.create(
                name=name,
                calle=request.POST.get('calle', ''),
                numero=request.POST.get('numero', ''),
                colonia=request.POST.get('colonia', ''),
                cp=request.POST.get('cp', ''),
                ciudad=request.POST.get('ciudad', ''),
                estado=request.POST.get('estado', ''),
            )
            messages.success(request, 'Sucursal creada.')
            return redirect('sucursales')
    return render(request, 'crear_sucursal.html')


@login_required
def editar_sucursal(request, branch_id):
    branch = Branch.objects.get(pk=branch_id)
    if request.method == 'POST':
        branch.name = request.POST.get('name', branch.name)
        branch.calle = request.POST.get('calle', branch.calle)
        branch.numero = request.POST.get('numero', branch.numero)
        branch.colonia = request.POST.get('colonia', branch.colonia)
        branch.cp = request.POST.get('cp', branch.cp)
        branch.ciudad = request.POST.get('ciudad', branch.ciudad)
        branch.estado = request.POST.get('estado', branch.estado)
        branch.save()
        messages.success(request, 'Sucursal actualizada.')
        return redirect('sucursales')
    return render(request, 'editar_sucursal.html', {'branch': branch})


@login_required
def eliminar_sucursal(request, branch_id):
    branch = Branch.objects.get(pk=branch_id)
    branch.active = False
    branch.save()
    messages.success(request, 'Sucursal desactivada.')
    return redirect('sucursales')


@login_required
def reportes_view(request):
    return render(request, 'reportes.html')


@login_required
def exportar_vacaciones(request):
    return generate_excel_report(request, 'vacaciones')


@login_required
def exportar_permisos(request):
    return generate_excel_report(request, 'permisos')


@login_required
def exportar_ausencias(request):
    return generate_excel_report(request, 'ausencias')


@login_required
def mi_espacio(request):
    return render(request, 'mi_espacio.html')


@login_required
def mi_perfil(request):
    return render(request, 'mi_perfil.html')


@login_required
def mis_solicitudes(request):
    return render(request, 'mis_solicitudes.html')


@login_required
def nueva_solicitud(request):
    if request.method == 'POST':
        form = RequestForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Solicitud creada.')
            return redirect('mis_solicitudes')
    else:
        form = RequestForm()
    return render(request, 'nueva_solicitud.html', {'form': form})


@login_required
def usuarios_view(request):
    users = User.objects.all().order_by('username')
    return render(request, 'usuarios.html', {'users': users})


@login_required
def crear_usuario(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        role = request.POST.get('role', 'user')
        password = request.POST.get('password', '')
        if username and password:
            User.objects.create_user(
                username=username,
                email=email,
                first_name=first_name,
                last_name=last_name,
                role=role,
                password=password,
            )
            messages.success(request, 'Usuario creado.')
            return redirect('usuarios')
    return render(request, 'crear_usuario.html')


@login_required
def editar_usuario(request, user_id):
    user = User.objects.get(pk=user_id)
    if request.method == 'POST':
        user.email = request.POST.get('email', user.email)
        user.first_name = request.POST.get('first_name', user.first_name)
        user.last_name = request.POST.get('last_name', user.last_name)
        user.role = request.POST.get('role', user.role)
        user.is_active = bool(request.POST.get('is_active'))
        password = request.POST.get('password', '')
        if password:
            user.set_password(password)
        user.save()
        messages.success(request, 'Usuario actualizado.')
        return redirect('usuarios')
    return render(request, 'editar_usuario.html', {'target_user': user})


@login_required
def generar_api_key(request, user_id):
    user = User.objects.get(pk=user_id)
    from employees.authentication import generate_api_key
    user.api_key = generate_api_key()
    user.save()
    messages.success(request, f'API Key generada para {user.username}.')
    return redirect('usuarios')


@login_required
def revocar_api_key(request, user_id):
    user = User.objects.get(pk=user_id)
    user.api_key = None
    user.save()
    messages.success(request, f'API Key revocada para {user.username}.')
    return redirect('usuarios')


@login_required
def eliminar_usuario(request, user_id):
    user = User.objects.get(pk=user_id)
    user.is_active = False
    user.save()
    messages.success(request, f'Usuario {user.username} desactivado.')
    return redirect('usuarios')


@login_required
def restaurar_usuario(request, user_id):
    user = User.objects.get(pk=user_id)
    user.is_active = True
    user.save()
    messages.success(request, f'Usuario {user.username} restaurado.')
    return redirect('usuarios')


@login_required
def mi_perfil_view(request):
    if request.method == 'POST':
        request.user.first_name = request.POST.get('first_name', request.user.first_name)
        request.user.last_name = request.POST.get('last_name', request.user.last_name)
        request.user.email = request.POST.get('email', request.user.email)
        password = request.POST.get('password', '')
        if password:
            request.user.set_password(password)
        request.user.save()
        messages.success(request, 'Perfil actualizado.')
        return redirect('mi_perfil')
    return render(request, 'mi_perfil_edit.html')


@login_required
def empleados_crud_view(request):
    employees = Employee.objects.select_related('user', 'branch').filter(status='activo')
    return render(request, 'empleados_crud.html', {'employees': employees})


@login_required
def crear_empleado(request):
    return render(request, 'crear_empleado.html')


@login_required
def editar_empleado(request, employee_id):
    employee = Employee.objects.get(pk=employee_id)
    return render(request, 'editar_empleado.html', {'employee': employee})


@login_required
def eliminar_empleado(request, employee_id):
    employee = Employee.objects.get(pk=employee_id)
    employee.status = 'baja'
    employee.save()
    messages.success(request, f'Empleado {employee} dado de baja.')
    return redirect('empleados_crud')


@login_required
def recontratar_empleado(request, employee_id):
    employee = Employee.objects.get(pk=employee_id)
    employee.status = 'activo'
    employee.save()
    messages.success(request, f'Empleado {employee} recontratado.')
    return redirect('empleados_crud')


@login_required
def eliminar_permanente_empleado(request, employee_id):
    employee = Employee.objects.get(pk=employee_id)
    employee.delete()
    messages.success(request, 'Empleado eliminado permanentemente.')
    return redirect('empleados_crud')


@login_required
def settings_view(request):
    return render(request, 'settings.html')


def manifest_view(request):
    return render(request, 'manifest.json', content_type='application/json')


def service_worker_view(request):
    return render(request, 'service-worker.js', content_type='application/javascript')