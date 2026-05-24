"""Configuración de URLs del proyecto HR Manager.

Incluye:
- Admin Django
- API REST (core.urls)
- Vistas web del dashboard
- Webhook de Telegram Bot
"""

from django.contrib import admin
from django.http import JsonResponse
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from core.web_views import (
    login_view, logout_view, dashboard,
    empleados_view, solicitudes_view, solicitudes_pendientes_view,
    ausencias_view, registrar_ausencia,
    sucursales_view,
    reportes_view, exportar_vacaciones, exportar_permisos, exportar_ausencias,
    mi_perfil, mis_solicitudes, nueva_solicitud, mi_espacio,
    usuarios_view, editar_usuario, crear_usuario, mi_perfil_view,
    crear_sucursal, editar_sucursal, eliminar_sucursal,
    empleados_crud_view, crear_empleado, editar_empleado, eliminar_empleado,
    generar_api_key, revocar_api_key,
    settings_view, eliminar_usuario, restaurar_usuario,
    manifest_view, service_worker_view,
    recontratar_empleado, eliminar_permanente_empleado,
)

from telegram_bot.views import webhook
from core.report_views import auditoria_view, metricas_view
from core.hq_auth import hq_sso_login

urlpatterns = [
    path('healthz', lambda r: JsonResponse({'ok': True, 'service': 'hrmgr'}), name='healthz'),
    path('admin/', admin.site.urls),
    path('api/', include('core.urls')),
    path('auth/hq', hq_sso_login, name='hq_sso_login'),
    path('', login_view, name='login'),
    path('dashboard/', dashboard, name='dashboard'),
    path('logout/', logout_view, name='logout'),
    path('empleados/', empleados_view, name='empleados'),
    path('solicitudes/', solicitudes_view, name='solicitudes'),
    path('solicitudes/pendientes/', solicitudes_pendientes_view, name='solicitudes_pendientes'),
    path('ausencias/', ausencias_view, name='ausencias'),
    path('ausencias/registrar/', registrar_ausencia, name='registrar_ausencia'),
    path('sucursales/', sucursales_view, name='sucursales'),
    path('reportes/', reportes_view, name='reportes'),
    path('reportes/vacaciones/', exportar_vacaciones, name='exportar_vacaciones'),
    path('reportes/permisos/', exportar_permisos, name='exportar_permisos'),
    path('reportes/ausencias/', exportar_ausencias, name='exportar_ausencias'),
    path('mi-espacio/', mi_espacio, name='mi_espacio'),
    path('mi-perfil/', mi_perfil, name='mi_perfil'),
    path('mis-solicitudes/', mis_solicitudes, name='mis_solicitudes'),
    path('nueva-solicitud/', nueva_solicitud, name='nueva_solicitud'),
    path('telegram/webhook/', webhook, name='telegram_webhook'),
    path('auditoria/', auditoria_view, name='auditoria'),
    path('metricas/', metricas_view, name='metricas'),
    path('usuarios/', usuarios_view, name='usuarios'),
    path('usuarios/crear/', crear_usuario, name='crear_usuario'),
    path('usuarios/<int:user_id>/editar/', editar_usuario, name='editar_usuario'),
    path('usuarios/<int:user_id>/api-key/generar/', generar_api_key, name='generar_api_key'),
    path('usuarios/<int:user_id>/api-key/revocar/', revocar_api_key, name='revocar_api_key'),
    path('usuarios/<int:user_id>/eliminar/', eliminar_usuario, name='eliminar_usuario'),
    path('usuarios/<int:user_id>/restaurar/', restaurar_usuario, name='restaurar_usuario'),
    path('mi-perfil/editar/', mi_perfil_view, name='mi_perfil_edit'),

    path('sucursales/crear/', crear_sucursal, name='crear_sucursal'),
    path('sucursales/<int:branch_id>/editar/', editar_sucursal, name='editar_sucursal'),
    path('sucursales/<int:branch_id>/eliminar/', eliminar_sucursal, name='eliminar_sucursal'),

    path('empleados-crud/', empleados_crud_view, name='empleados_crud'),
    path('empleados/crear/', crear_empleado, name='crear_empleado'),
    path('empleados/<int:employee_id>/editar/', editar_empleado, name='editar_empleado'),
    path('empleados/<int:employee_id>/eliminar/', eliminar_empleado, name='eliminar_empleado'),
    path('empleados/<int:employee_id>/recontratar/', recontratar_empleado, name='recontratar_empleado'),
    path('empleados/<int:employee_id>/eliminar-permanente/', eliminar_permanente_empleado, name='eliminar_permanente_empleado'),
    path('settings/', settings_view, name='settings'),
    path('manifest.json', manifest_view, name='manifest'),
    path('service-worker.js', service_worker_view, name='service_worker'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)