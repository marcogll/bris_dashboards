"""Decoradores de seguridad para vistas web."""

import time
from functools import wraps

from django.core.cache import cache
from django.http import HttpResponse


def rate_limit(max_requests=10, window=60):
    """Limit requests per IP within a time window."""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            ip = request.META.get('REMOTE_ADDR', '')
            key = f'rate_limit:{ip}:{view_func.__name__}'
            current = cache.get(key, 0)
            if current >= max_requests:
                return HttpResponse(
                    'Demasiadas peticiones. Intente nuevamente más tarde.',
                    status=429,
                )
            cache.set(key, current + 1, window)
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator