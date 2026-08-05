"""User Entity Model for Identity Management in Investiga.

This module defines the User domain entity representing authenticated principals,
operators, and incident responders in the platform.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from app.auth.models.associations import user_roles
from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.auth.models.role import Role


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """Core domain entity representing a human engineer, analyst, or system account.

    Attributes:
        id: Globally unique UUID primary key.
        email: Canonical, unique email address used for identity authentication.
        hashed_password: Secure Argon2id cryptographic hash (never plaintext).
        full_name: User's legal or professional display name.
        is_active: Boolean flag for immediate administrative account deactivation.
        is_verified: Flag indicating whether email ownership has been verified.
        is_superuser: Flag granting root-level administrative authorization bypass.
        last_login_at: UTC audit timestamp of the user's most recent successful login.
        tenant_id: Optional UUID of the tenant organization (multi-tenancy preparation).
        created_at: UTC timestamp of account creation.
        updated_at: UTC timestamp of last record update.
        is_deleted: Soft-delete audit flag preserving referential integrity.
        deleted_at: UTC timestamp when account was soft-deleted.
        roles: Many-to-many relationship linking roles assigned to this user.
    """

    @declared_attr.directive
    def __tablename__(cls) -> str:
        return "users"

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
        doc="Unique user email address.",
    )
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Argon2id password hash string.",
    )
    full_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Full name of the user.",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
        doc="Status flag enabling or disabling account access.",
    )
    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        doc="Status flag confirming email verification.",
    )
    is_superuser: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        doc="Status flag granting global superuser privileges.",
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        default=None,
        nullable=True,
        doc="UTC timestamp of the most recent authentication.",
    )
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
        doc="Tenant organization identifier for multi-tenant isolation.",
    )

    # Relationships
    roles: Mapped[list["Role"]] = relationship(
        "Role",
        secondary=user_roles,
        back_populates="users",
        lazy="selectin",
    )

    def __init__(
        self,
        *,
        email: str,
        hashed_password: str,
        full_name: str,
        is_active: bool = True,
        is_verified: bool = False,
        is_superuser: bool = False,
        is_deleted: bool = False,
        deleted_at: datetime | None = None,
        tenant_id: uuid.UUID | None = None,
        last_login_at: datetime | None = None,
        id: uuid.UUID | None = None,
        roles: list["Role"] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            email=email,
            hashed_password=hashed_password,
            full_name=full_name,
            is_active=is_active,
            is_verified=is_verified,
            is_superuser=is_superuser,
            is_deleted=is_deleted,
            deleted_at=deleted_at,
            tenant_id=tenant_id,
            last_login_at=last_login_at,
            id=id,
            roles=roles if roles is not None else [],
            **kwargs,
        )

    @property
    def role_names(self) -> list[str]:
        """Convenience property returning a list of active role names."""
        return [role.name for role in self.roles if not role.is_deleted]

    @property
    def permission_codes(self) -> set[str]:
        """Convenience property aggregating all distinct permission codes across assigned roles."""
        perms: set[str] = set()
        for role in self.roles:
            if not role.is_deleted:
                for permission in role.permissions:
                    perms.add(permission.code)
        return perms

    def __repr__(self) -> str:
        return (
            f"<User id={self.id} email='{self.email}' "
            f"active={self.is_active} superuser={self.is_superuser}>"
        )
