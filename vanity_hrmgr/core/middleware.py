"""Middleware de seguridad OWASP para headers adicionales."""

from django.utils.deprecation import MiddlewareMixin


class SecurityHeadersMiddleware(MiddlewareMixin):
    """Agrega headers de seguridad adicionales para protección OWASP.

    Headers implementados:
    - X-XSS-Protection: Protección contra XSS
    - X-Content-Type-Options: Previene MIME sniffing
    - X-Frame-Options: Previene clickjacking
    - Referrer-Policy: Control de información de referencia
    - Permissions-Policy: Restricción de APIs del navegador
    """

    def process_response(self, request, response):
        response['X-XSS-Protection'] = '1; mode=block'
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'

        if not request.is_secure():
            response['X-Forwarded-Proto'] = 'https'

        return response