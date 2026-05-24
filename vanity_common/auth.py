from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from functools import wraps
from typing import Any
from uuid import UUID

from flask import current_app, flash, g, redirect, request, session, url_for
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from .models import Permission, User
from .session import _hash_token, revoke_session
from .supabase_client import get_supabase

TOKEN_MAX_AGE = 43200


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

    token_hash = _hash_token(token)
    sb = get_supabase()

    active_sessions = sb.table("vanity_sessions").select("id").eq("session_token_hash", token_hash).is_("revoked_at", "null").execute().data
    session_exists = False
    for s in active_sessions:
        row = sb.table("vanity_sessions").select("expires_at").eq("id", s["id"]).execute().data
        if row:
            exp = row[0].get("expires_at")
            if exp:
                exp_dt = datetime.fromisoformat(exp) if isinstance(exp, str) else exp
                if exp_dt.tzinfo is None:
                    exp_dt = exp_dt.replace(tzinfo=timezone.utc)
                if exp_dt > datetime.now(timezone.utc):
                    session_exists = True
                    break

    if not session_exists:
        raise BadSignature("session revoked or expired")

    user_id = data.get("user_id")
    user_rows = sb.table("vanity_users").select("*, vanity_roles!vanity_users_role_id_fkey(name, level)").eq("id", str(user_id)).eq("is_active", True).execute().data
    if not user_rows:
        raise BadSignature("user not found or inactive")
    r = user_rows[0]
    role = r.pop("vanity_roles", {}) or {}
    r["role_name"] = role.get("name", "")
    r["role_level"] = role.get("level", 0)

    return User.from_supabase_row(r), data


def has_permission(user: User, system: str, module: str, action: str) -> bool:
    """Check whether *user* has an effective allow on (system, module, action).

    User-level overrides take precedence over role-level permissions.
    """
    sb = get_supabase()
    user_perm = sb.table("vanity_permissions").select("allowed").eq("subject_type", "user").eq("subject_id", str(user.id)).eq("system", system).eq("module", module).eq("action", action).execute().data
    if user_perm:
        return bool(user_perm[0]["allowed"])

    role_perm = sb.table("vanity_permissions").select("allowed").eq("subject_type", "role").eq("subject_id", str(user.role_id)).eq("system", system).eq("module", module).eq("action", action).execute().data
    return bool(role_perm and role_perm[0]["allowed"])


def get_permissions_for_user(user: User) -> list[dict[str, Any]]:
    """Return merged list of effective permissions for *user* (role + overrides)."""
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


def load_user_from_session():
    """Call from a before_request hook to populate g.hq_user."""
    user_id = session.get("user_id")
    if not user_id:
        g.hq_user = None
        return

    sb = get_supabase()
    rows = sb.table("vanity_users").select("*, vanity_roles!vanity_users_role_id_fkey(name, level)").eq("id", str(user_id)).eq("is_active", True).execute().data
    if not rows:
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