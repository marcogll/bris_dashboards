from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from functools import wraps
from typing import Any
from uuid import UUID

from flask import current_app, flash, g, redirect, request, session, url_for
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from .models import Permission, User
from .session import _hash_token, revoke_session
from .supabase_client import get_supabase

import os

logger = logging.getLogger("vanity_common.auth")

TOKEN_MAX_AGE = 43200


def _is_supabase_configured() -> bool:
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_KEY", "")
    return bool(url and key and "placeholder" not in key.lower() and key != "")


def validate_hq_token(token: str, expected_system: str | None = None) -> tuple[User, dict[str, Any]]:
    """Validate an SSO token from HQ Wrapper.

    First validates the itsdangerous signature, then checks that the session
    has not been revoked in Supabase. Returns (user, token_data).
    """
    secret = current_app.config.get("SECRET_KEY") or current_app.config.get("VANITY_HQ_SECRET_KEY", "dev-secret-change-me")
    serializer = URLSafeTimedSerializer(secret, salt="vanity-hq-app-token")
    data = serializer.loads(token, max_age=TOKEN_MAX_AGE)

    if expected_system and data.get("system") != expected_system:
        raise BadSignature("system mismatch")

    if not _is_supabase_configured():
        # Fallback local validation
        context = data.get("context", {})
        user_data = context.get("user", {})
        u = User(
            id=UUID(user_data["id"]) if isinstance(user_data["id"], str) else user_data["id"],
            username=user_data["username"],
            email=user_data["email"],
            name=user_data["name"],
            role_id=UUID("00000000-0000-0000-0000-000000000000"),
            role_name=user_data["role"],
            role_level=user_data["level"],
            is_active=True,
            theme=context.get("theme", "dark"),
        )
        return u, data

    token_hash = _hash_token(token)
    sb = get_supabase()

    active_sessions = sb.table("vanity_sessions").select("id, expires_at").eq("session_token_hash", token_hash).is_("revoked_at", "null").execute().data
    session_exists = False
    for s in active_sessions:
        exp = s.get("expires_at")
        if exp:
            exp_dt = datetime.fromisoformat(exp) if isinstance(exp, str) else exp
            if exp_dt.tzinfo is None:
                exp_dt = exp_dt.replace(tzinfo=timezone.utc)
            if exp_dt > datetime.now(timezone.utc):
                session_exists = True
                break

    if not session_exists:
        logger.warning("Token rejected: no active session for user=%s system=%s", data.get("user_id"), data.get("system"))
        raise BadSignature("session revoked or expired")

    user_id = data.get("user_id")
    user_rows = sb.table("vanity_users").select("*, vanity_roles!vanity_users_role_id_fkey(name, level)").eq("id", str(user_id)).eq("is_active", True).execute().data
    if not user_rows:
        raise BadSignature("user not found or inactive")
    r = user_rows[0]
    role = r.pop("vanity_roles", {}) or {}
    r["role_name"] = role.get("name", "")
    r["role_level"] = role.get("level", 0)

    logger.info("Token validated: user=%s system=%s role=%s", r.get("username") or r.get("email"), data.get("system"), r["role_name"])
    return User.from_supabase_row(r), data


def _session_permissions() -> list[dict[str, Any]]:
    """Return permissions from session, checking both hq_context and direct keys."""
    return session.get("permissions") or session.get("hq_context", {}).get("permissions", [])


def has_permission(user: User, system: str, module: str, action: str) -> bool:
    """Check whether *user* has an effective allow on (system, module, action).

    User-level overrides take precedence over role-level permissions.
    """
    if not _is_supabase_configured():
        return any(
            p["system"] == system and p["module"] == module and p["action"] == action
            for p in _session_permissions()
        )

    sb = get_supabase()
    user_perm = sb.table("vanity_permissions").select("allowed").eq("subject_type", "user").eq("subject_id", str(user.id)).eq("system", system).eq("module", module).eq("action", action).execute().data
    if user_perm:
        return bool(user_perm[0]["allowed"])

    role_perm = sb.table("vanity_permissions").select("allowed").eq("subject_type", "role").eq("subject_id", str(user.role_id)).eq("system", system).eq("module", module).eq("action", action).execute().data
    return bool(role_perm and role_perm[0]["allowed"])


def get_permissions_for_user(user: User) -> list[dict[str, Any]]:
    """Return merged list of effective permissions for *user* (role + overrides)."""
    if not _is_supabase_configured():
        return _session_permissions()

    sb = get_supabase()
    role_rows = sb.table("vanity_permissions").select("system, module, action, scope, allowed").eq("subject_type", "role").eq("subject_id", str(user.role_id)).execute().data
    user_rows = sb.table("vanity_permissions").select("system, module, action, scope, allowed").eq("subject_type", "user").eq("subject_id", str(user.id)).execute().data
    overrides = {(r["system"], r["module"], r["action"]): r for r in user_rows}
    result = []
    for r in role_rows:
        key = (r["system"], r["module"], r["action"])
        effective = overrides.get(key, r)
        if effective["allowed"]:
            result.append({
                "system": effective["system"],
                "module": effective["module"],
                "action": effective["action"],
                "scope": effective["scope"],
            })
    return result


def login_required(fn):
    """Decorator: redirect to HQ for re-auth if user not in session."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not g.get("hq_user"):
            hq_url = current_app.config.get("VANITY_HQ_PUBLIC_URL", "/hq")
            return redirect(f"{hq_url}/login?next={request.path}")
        return fn(*args, **kwargs)
    return wrapper


def require_permission(system: str, module: str, action: str):
    """Decorator: redirect with flash if user lacks the given permission."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = g.get("hq_user")
            if not user:
                hq_url = current_app.config.get("VANITY_HQ_PUBLIC_URL", "/hq")
                return redirect(f"{hq_url}/login?next={request.path}")
            if not has_permission(user, system, module, action):
                flash("No tienes permiso para esa accion.", "warning")
                return redirect(url_for("dashboard") if "dashboard" in current_app.url_map._rules_by_endpoint else "/")
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def _load_user_from_session_data():
    """Fallback: load user from session data (for non-Supabase users)."""
    user_data = session.get("user") or session.get("hq_context", {}).get("user")
    if user_data:
        g.hq_user = User(
            id=UUID(user_data["id"]) if isinstance(user_data["id"], str) else user_data["id"],
            username=user_data["username"],
            email=user_data["email"],
            name=user_data["name"],
            password_hash="",
            phone=user_data.get("phone", ""),
            branch=user_data.get("branch", "all"),
            role_id=UUID("00000000-0000-0000-0000-000000000000"),
            role_name=user_data["role"],
            role_level=user_data["level"],
            is_active=True,
            theme=session.get("theme") or user_data.get("theme", "dark"),
        )
    else:
        g.hq_user = None


def load_user_from_session():
    """Call from a before_request hook to populate g.hq_user."""
    user_id = session.get("user_id")
    if not user_id:
        g.hq_user = None
        return

    if not _is_supabase_configured():
        _load_user_from_session_data()
        return

    try:
        UUID(str(user_id))
    except (ValueError, TypeError, AttributeError):
        logger.debug("User ID '%s' is not a UUID, falling back to session data", user_id)
        _load_user_from_session_data()
        return

    sb = get_supabase()
    try:
        rows = sb.table("vanity_users").select("*, vanity_roles!vanity_users_role_id_fkey(name, level)").eq("id", str(user_id)).eq("is_active", True).execute().data
    except Exception as exc:
        logger.warning("Supabase user lookup failed, falling back to session data: %s", exc)
        _load_user_from_session_data()
        return
    if not rows:
        logger.debug("User %s not found or inactive in Supabase", user_id)
        g.hq_user = None
        return
    r = rows[0]
    role = r.pop("vanity_roles", {}) or {}
    r["role_name"] = role.get("name", "")
    r["role_level"] = role.get("level", 0)
    g.hq_user = User.from_supabase_row(r)


def context_for_user(user: User) -> dict[str, Any]:
    SYSTEMS = current_app.config.get("VANITY_SYSTEMS", {})
    permissions = get_permissions_for_user(user)
    visible = {p["system"] for p in permissions if p["action"] == "view"}
    systems = {k: v for k, v in SYSTEMS.items() if k in visible}
    return {
        "user": {
            "id": str(user.id),
            "name": user.name,
            "email": user.email,
            "username": user.username,
            "role": user.role_name,
            "level": user.role_level,
            "branch": user.branch,
        },
        "theme": user.theme,
        "systems": [{"key": k, **v} for k, v in systems.items()],
        "permissions": permissions,
    }