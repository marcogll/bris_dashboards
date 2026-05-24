from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass
class Role:
    id: UUID
    name: str
    level: int
    description: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @classmethod
    def from_supabase_row(cls, row: dict[str, Any]) -> Role:
        return cls(
            id=UUID(row["id"]),
            name=row["name"],
            level=row["level"],
            description=row.get("description", ""),
            created_at=_parse_ts(row.get("created_at")),
            updated_at=_parse_ts(row.get("updated_at")),
        )


@dataclass
class User:
    id: UUID
    name: str
    email: str
    username: str
    password_hash: str
    phone: str = ""
    branch: str = "all"
    role_id: UUID | None = None
    role_name: str = ""
    role_level: int = 0
    theme: str = "system"
    is_active: bool = True
    last_login: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @classmethod
    def from_supabase_row(cls, row: dict[str, Any]) -> User:
        role_id = row.get("role_id")
        return cls(
            id=UUID(row["id"]),
            name=row["name"],
            email=row["email"],
            username=row["username"],
            password_hash=row.get("password_hash", ""),
            phone=row.get("phone", ""),
            branch=row.get("branch", "all"),
            role_id=UUID(role_id) if role_id else None,
            role_name=row.get("role_name", ""),
            role_level=row.get("role_level", 0),
            theme=row.get("theme", "system"),
            is_active=row.get("is_active", True),
            last_login=_parse_ts(row.get("last_login")),
            created_at=_parse_ts(row.get("created_at")),
            updated_at=_parse_ts(row.get("updated_at")),
        )


@dataclass
class Permission:
    id: UUID
    subject_type: str
    subject_id: UUID
    system: str
    module: str
    action: str
    scope: str = "none"
    allowed: bool = False
    created_at: datetime | None = None

    @classmethod
    def from_supabase_row(cls, row: dict[str, Any]) -> Permission:
        return cls(
            id=UUID(row["id"]),
            subject_type=row["subject_type"],
            subject_id=UUID(row["subject_id"]),
            system=row["system"],
            module=row["module"],
            action=row["action"],
            scope=row.get("scope", "none"),
            allowed=row.get("allowed", False),
            created_at=_parse_ts(row.get("created_at")),
        )


def _parse_ts(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))