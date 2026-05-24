"""Autenticación por API Key para integraciones machine-to-machine."""

import secrets

from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from .models import User


class APIKeyAuthentication(BaseAuthentication):
    """Autenticador que valida API Keys en el header Authorization."""

    keyword = 'ApiKey'

    def authenticate(self, request):
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')

        if not auth_header:
            return None

        parts = auth_header.split()

        if len(parts) != 2 or parts[0] != self.keyword:
            return None

        api_key = parts[1]

        if not api_key:
            return None

        try:
            user = User.objects.get(api_key=api_key)
        except User.DoesNotExist:
            raise AuthenticationFailed('API Key inválida')

        if not user.is_active:
            raise AuthenticationFailed('Usuario inactivo')

        return (user, None)

    def authenticate_header(self, request):
        return self.keyword


def generate_api_key():
    """Genera una API Key segura para usuarios."""
    return secrets.token_urlsafe(32)