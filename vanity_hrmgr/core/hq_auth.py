"""Autenticación SSO via HQ Wrapper para Vanity HRMgr.

Valida tokens emitidos por el HQ Wrapper (itsdangerous URLSafeTimedSerializer)
y crea/autentica usuarios Django automáticamente.

Flujo:
  1. HQ Wrapper lanza token en /launch/vanity_hrmgr
  2. Este servicio recibe token en /auth/hq?token=...
  3. Valida localmente con VANITY_HQ_SECRET_KEY, fallback a HQ API
  4. Se encuentra o crea un usuario Django con los datos del contexto
  5. django.contrib.auth.login() establece la sesión Django
  6. Redirige al dashboard
"""

import json
import logging
import urllib.error
import urllib.request

from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth import get_user_model
from django.http import HttpResponseRedirect
from django.urls import reverse

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

logger = logging.getLogger(__name__)

User = get_user_model()

SYSTEM_KEY = "vanity_hrmgr"

HQ_ROLE_TO_DJANGO_ROLE = {
    "Owner": "admin",
    "Admin": "admin",
    "Manager": "manager",
    "Operador": "user",
    "Solo lectura": "user",
    "Socia": "user",
}


def _serializer():
    return URLSafeTimedSerializer(
        settings.VANITY_HQ_SECRET_KEY,
        salt="vanity-hq-app-token",
    )


def validate_hq_token(token, expected_system=SYSTEM_KEY):
    """Validate an SSO token from HQ Wrapper.

    Tries local itsdangerous validation first, falls back to the HQ API.
    Returns the token context dict on success, raises on failure.
    """
    try:
        data = _serializer().loads(token, max_age=settings.VANITY_HQ_TOKEN_MAX_AGE)
        if expected_system and data.get("system") != expected_system:
            raise ValueError(
                f"Token system mismatch: expected {expected_system}, "
                f"got {data.get('system')}"
            )
        context = data.get("context")
        if context and context.get("user"):
            return context
        raise ValueError("Token missing user context")
    except (BadSignature, SignatureExpired):
        pass
    except ValueError:
        raise

    try:
        payload = json.dumps({"token": token, "system": expected_system}).encode()
        req = urllib.request.Request(
            f"{settings.VANITY_HQ_URL}/api/auth/validate-token",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            result = json.loads(response.read().decode())
        if not result.get("ok"):
            raise ValueError(result.get("error", "invalid token"))
        context = result.get("context")
        if context and context.get("user"):
            return context
        raise ValueError("Token missing user context from API")
    except urllib.error.URLError as exc:
        logger.error("HQ API unreachable: %s", exc)
        raise ValueError("No se pudo validar la sesión HQ.") from exc


def _find_or_create_user(context):
    """Find or create a Django User from the HQ token context."""
    hq_user = context.get("user", {})
    hq_user_id = hq_user.get("id")
    hq_email = hq_user.get("email", "").strip().lower()
    hq_name = hq_user.get("name", "")
    hq_role = hq_user.get("role", "Operador")
    hq_username = hq_user.get("username", "")

    django_role = HQ_ROLE_TO_DJANGO_ROLE.get(hq_role, "user")

    user = None

    if hq_email:
        user = User.objects.filter(email=hq_email).first()

    if user is None and hq_username:
        user = User.objects.filter(username=hq_username).first()

    if user is None and hq_user_id is not None:
        user = User.objects.filter(username=f"hq_{hq_user_id}").first()

    if user is None:
        username = hq_username or (f"hq_{hq_user_id}" if hq_user_id else None)
        if not username:
            return None

        create_kwargs = {
            "username": username,
            "role": django_role,
        }
        if hq_email:
            create_kwargs["email"] = hq_email
        if hq_name:
            create_kwargs["first_name"] = hq_name.split()[0] if hq_name else ""
            parts = hq_name.split()
            create_kwargs["last_name"] = " ".join(parts[1:]) if len(parts) > 1 else ""

        user = User.objects.create_user(**create_kwargs)
        user.set_unusable_password()
        user.save()
        logger.info("Created Django user %s from HQ user %s", user.username, hq_user_id)
    else:
        changed = False
        if hq_email and user.email != hq_email:
            user.email = hq_email
            changed = True
        if hq_name:
            first = hq_name.split()[0] if hq_name else ""
            last = " ".join(hq_name.split()[1:]) if len(hq_name.split()) > 1 else ""
            if user.first_name != first:
                user.first_name = first
                changed = True
            if user.last_name != last:
                user.last_name = last
                changed = True
        if user.role != django_role:
            user.role = django_role
            changed = True
        if changed:
            user.save()

    return user


def hq_sso_login(request):
    """Django view: validates HQ SSO token and logs the user in."""
    token = request.GET.get("token", "").strip()
    if not token:
        from django.contrib import messages
        messages.error(request, "Token faltante.")
        return HttpResponseRedirect(reverse("login"))

    try:
        context = validate_hq_token(token)
    except Exception:
        from django.contrib import messages
        messages.error(request, "No se pudo validar la sesión HQ.")
        return HttpResponseRedirect(reverse("login"))

    user = _find_or_create_user(context)
    if user is None:
        from django.contrib import messages
        messages.error(request, "No se pudo crear el usuario desde HQ.")
        return HttpResponseRedirect(reverse("login"))

    if not user.is_active:
        from django.contrib import messages
        messages.error(request, "Usuario inactivo.")
        return HttpResponseRedirect(reverse("login"))

    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    request.session["hq_context"] = context
    request.session["hq_token"] = token

    logger.info("HQ SSO login for user %s (HQ id %s)", user.username, context.get("user", {}).get("id"))

    next_url = request.GET.get("next") or reverse("dashboard")
    return HttpResponseRedirect(next_url)