"""Role Entity Model for Role-Based Access Control (RBAC) in Investiga.

This module defines the Role domain entity which aggregates discrete permissions
and maps them to users within the platform.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from app.auth.models.associations import role_permissions, user_roles
from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.auth.models.permission import Permission
    from app.auth.models.user import User


class Role(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """Domain entity grouping authorization permissions into functional profiles.

    Roles can be pre-configured system roles (e.g., 'admin', 'investigator', 'viewer')
    or tenant-customized operational roles.

    Attributes:
        id: Globally unique UUID primary key.
        name: Unique machine-readable role identifier (e.g., 'admin', 'incident_commander').
        display_name: Human-friendly name displayed in UI dashboards.
        description: Operational summary of the role's intended usage.
        is_system_role: Guard flag preventing critical built-in roles from accidental deletion.
        tenant_id: Optional UUID of the tenant organization (multi-tenancy preparation).
        created_at: UTC timestamp when the role was created.
        updated_at: UTC timestamp when the role definition was last modified.
        is_deleted: Soft-delete audit flag.
        deleted_at: UTC timestamp when soft-deleted.
        users: Many-to-many relationship linking users assigned to this role.
        permissions: Many-to-many relationship linking permissions granted to this role.
    """

    @declared_attr.directive
    def __tablename__(cls) -> str:
        return "roles"

    name: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False,
        doc="Unique machine-readable role key.",
    )
    display_name: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        doc="Human-readable display name for the role.",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Description of capabilities granted by this role.",
    )
    is_system_role: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        doc="Flag indicating immutable built-in platform system role.",
    )
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
        doc="Tenant organization identifier for multi-tenant isolation.",
    )

    # Relationships
    users: Mapped[list["User"]] = relationship(
        "User",
        secondary=user_roles,
        back_populates="roles",
        lazy="selectin",
    )
    permissions: Mapped[list["Permission"]] = relationship(
        "Permission",
        secondary=role_permissions,
        back_populates="roles",
        lazy="selectin",
    )

    def __init__(
        self,
        *,
        name: str,
        display_name: str,
        description: str | None = None,
        is_system_role: bool = False,
        is_deleted: bool = False,
        deleted_at: datetime | None = None,
        tenant_id: uuid.UUID | None = None,
        id: uuid.UUID | None = None,
        permissions: list["Permission"] | None = None,
        users: list["User"] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            name=name,
            display_name=display_name,
            description=description,
            is_system_role=is_system_role,
            is_deleted=is_deleted,
            deleted_at=deleted_at,
            tenant_id=tenant_id,
            id=id,
            permissions=permissions if permissions is not None else [],
            users=users if users is not None else [],
            **kwargs,
        )

    def __repr__(self) -> str:
        return f"<Role id={self.id} name='{self.name}' system={self.is_system_role}>"
