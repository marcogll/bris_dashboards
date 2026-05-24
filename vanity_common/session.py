from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from flask import Flask, g, request, session
from flask.sessions import SessionInterface, SecureCookieSession

from .supabase_client import get_supabase


class SupabaseSessionInterface(SessionInterface):
    """Flask session interface backed by the vanity_sessions table in Supabase.

    The browser cookie stores only the session UUID. On each request the full
    context (user info, theme, permissions) is loaded from Supabase, making
    sessions instantly revocable server-side.
    """

    sess_cookie_name = "vanity_session"

    def open_session(self, app: Flask, request) -> SecureCookieSession | None:
        sid = request.cookies.get(self.sess_cookie_name)
        if not sid:
            return None
        try:
            sess = _load_session(sid)
        except Exception:
            return None
        if sess is None:
            return None
        s = SecureCookieSession()
        s.update(sess.get("context", {}))
        s["_session_id"] = sid
        s.modified = False
        return s

    def save_session(self, app: Flask, session: SecureCookieSession, response) -> None:
        sid = session.get("_session_id")
        if not sid:
            return
        context = {k: v for k, v in session.items() if k != "_session_id"}
        _update_session_context(sid, context)
        domain = self.get_cookie_domain(app)
        path = self.get_cookie_path(app)
        if session.get("_fresh"):
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


def create_session(user_id: UUID, system: str, context: dict[str, Any], token: str, max_age_seconds: int = 43200) -> str:
    """Create a new session row in Supabase and return the session UUID."""
    from .models import _parse_ts

    token_hash = _hash_token(token)
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=max_age_seconds)
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
    return row["id"]


def revoke_session(session_id: str) -> None:
    """Mark a session as revoked (logout)."""
    sb = get_supabase()
    sb.table("vanity_sessions").update({
        "revoked_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", session_id).execute()


def revoke_sessions_for_user(user_id: str | UUID, system: str | None = None) -> None:
    """Revoke all active sessions for a user, optionally scoped to one system."""
    sb = get_supabase()
    q = sb.table("vanity_sessions").update({
        "revoked_at": datetime.now(timezone.utc).isoformat(),
    }).eq("user_id", str(user_id)).is_("revoked_at", "null")
    if system:
        q = q.eq("system", system)
    q.execute()


def _load_session(session_id: str) -> dict[str, Any] | None:
    """Load an active session from Supabase by id."""
    sb = get_supabase()
    rows = sb.table("vanity_sessions").select("*").eq("id", session_id).is_("revoked_at", "null").execute().data
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
    sb.table("vanity_sessions").update(updates).eq("id", session_id).execute()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()