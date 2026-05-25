from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from flask import Flask, g, request, session
from flask.sessions import SecureCookieSessionInterface, SecureCookieSession
import os

from .supabase_client import get_supabase

logger = logging.getLogger("vanity_common.session")


class SupabaseSessionInterface(SecureCookieSessionInterface):
    """Flask session interface backed by the vanity_sessions table in Supabase.

    The browser cookie stores only the session UUID. On each request the full
    context (user info, theme, permissions) is loaded from Supabase, making
    sessions instantly revocable server-side.

    If Supabase keys are placeholders or empty, it falls back to standard cookie-based sessions.
    """

    sess_cookie_name = "vanity_session"

    def _is_supabase_configured(self) -> bool:
        url = os.environ.get("SUPABASE_URL", "")
        key = os.environ.get("SUPABASE_SERVICE_KEY", "")
        return bool(url and key and "placeholder" not in key.lower() and key != "")

    def open_session(self, app: Flask, request) -> SecureCookieSession | None:
        if not self._is_supabase_configured():
            return super().open_session(app, request)

        sid = request.cookies.get(self.sess_cookie_name)
        if sid:
            try:
                sess = _load_session(sid)
            except Exception:
                sess = None
            if sess is not None:
                s = SecureCookieSession()
                s.update(sess.get("context", {}))
                s["_session_id"] = sid
                s.modified = False
                return s
        return super().open_session(app, request)

    def save_session(self, app: Flask, session: SecureCookieSession, response) -> None:
        if not self._is_supabase_configured():
            return super().save_session(app, session, response)

        sid = session.get("_session_id")
        if not sid and not session:
            return
        if not sid:
            return super().save_session(app, session, response)
        context = {k: v for k, v in session.items() if k != "_session_id" and not k.startswith("_")}
        if sid:
            _update_session_context(sid, context)
        domain = self.get_cookie_domain(app)
        path = self.get_cookie_path(app)
        if session.get("_fresh") or session.modified:
            if not sid:
                logger.warning("Session save without _session_id — set_cookie skipped")
                return
            response.set_cookie(
                self.sess_cookie_name,
                sid,
                httponly=True,
                secure=app.config.get("SESSION_COOKIE_SECURE", False),
                samesite=app.config.get("SESSION_COOKIE_SAMESITE", "Lax"),
                domain=domain,
                path=path,
                max_age=app.config.get("PERMANENT_SESSION_LIFETIME", timedelta(days=7)).total_seconds(),
            )


def create_session(user_id: UUID, system: str, context: dict[str, Any], token: str, max_age_seconds: int = 43200) -> str | None:
    """Create a new session row in Supabase and return the session UUID.
    Returns None when the user_id is not a valid UUID (Supabase incompatible)."""
    try:
        UUID(str(user_id))
    except (ValueError, AttributeError, TypeError):
        logger.warning("Supabase session skipped — user_id '%s' is not a UUID, using cookie session", str(user_id)[:8])
        return None

    token_hash = _hash_token(token)
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=max_age_seconds)
    try:
        sb = get_supabase()
        row = sb.table("vanity_sessions").insert({
            "user_id": str(user_id),
            "session_token_hash": token_hash,
            "system": system,
            "context": context,
            "ip_address": "",
            "user_agent": "",
            "expires_at": expires_at.isoformat(),
        }).execute().data[0]
        logger.info("Created session for user=%s system=%s expires=%s", str(user_id)[:8], system, expires_at.isoformat())
        return row["id"]
    except Exception as exc:
        logger.warning("Supabase session creation failed, using local session: %s", exc)
        import uuid
        return str(uuid.uuid4())


def revoke_session(session_id: str) -> None:
    """Mark a session as revoked (logout)."""
    sb = get_supabase()
    sb.table("vanity_sessions").update({
        "revoked_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", session_id).execute()
    logger.info("Revoked session %s", session_id[:8])


def revoke_sessions_for_user(user_id: str | UUID, system: str | None = None) -> None:
    """Revoke all active sessions for a user, optionally scoped to one system."""
    sb = get_supabase()
    q = sb.table("vanity_sessions").update({
        "revoked_at": datetime.now(timezone.utc).isoformat(),
    }).eq("user_id", str(user_id)).is_("revoked_at", "null")
    if system:
        q = q.eq("system", system)
    result = q.execute()
    count = len(result.data) if result.data else 0
    logger.info("Revoked %d sessions for user=%s system=%s", count, str(user_id)[:8], system or "all")


def _load_session(session_id: str) -> dict[str, Any] | None:
    """Load an active session from Supabase by id."""
    try:
        sb = get_supabase()
        rows = sb.table("vanity_sessions").select("*").eq("id", session_id).is_("revoked_at", "null").execute().data
    except Exception as exc:
        logger.warning("Failed to load session from Supabase: %s", exc)
        return None
    if not rows:
        return None
    row = rows[0]
    expires_at = row.get("expires_at")
    if expires_at:
        exp = datetime.fromisoformat(expires_at) if isinstance(expires_at, str) else expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp < datetime.now(timezone.utc):
            return None
    return row


def _update_session_context(session_id: str, context: dict[str, Any]) -> None:
    sb = get_supabase()
    updates = {"context": context}
    try:
        from flask import request as _req
        updates["ip_address"] = _req.remote_addr or ""
        updates["user_agent"] = _req.headers.get("User-Agent", "")
    except RuntimeError:
        pass
    try:
        sb.table("vanity_sessions").update(updates).eq("id", session_id).execute()
    except Exception as exc:
        logger.warning("Failed to update Supabase session %s: %s", session_id[:8], exc)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()