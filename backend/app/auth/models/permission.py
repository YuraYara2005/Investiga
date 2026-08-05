"""Permission Entity Model for Fine-Grained Authorization in Investiga.

This module defines the Permission domain entity representing discrete operational
capabilities on platform resources (e.g. 'investigations:create', 'knowledge:ingest').
"""

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from app.auth.models.associations import role_permissions
from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.auth.models.role import Role


class Permission(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Discrete operational authorization entitlement.

    Permissions represent atomic actions that can be executed against platform resources.
    Roles group one or more permissions together.

    Attributes:
        id: Globally unique UUID primary key.
        code: Unique canonical permission string formatted as '{resource}:{action}'
              (e.g., 'investigations:create', 'evidence:read', 'ai_pipeline:execute').
        resource: Target domain resource namespace (e.g., 'investigations', 'knowledge', 'users').
        action: Permitted action verb (e.g., 'create', 'read', 'update', 'delete', 'execute').
        description: Human-readable documentation of what this entitlement grants.
        created_at: UTC timestamp of permission definition creation.
        updated_at: UTC timestamp of last metadata modification.
        roles: Many-to-many relationship linking roles endowed with this permission.
    """

    @declared_attr.directive
    def __tablename__(cls) -> str:
        return "permissions"

    code: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
        nullable=False,
        doc="Canonical dot/colon formatted permission identifier.",
    )
    resource: Mapped[str] = mapped_column(
        String(50),
        index=True,
        nullable=False,
        doc="Target resource domain namespace.",
    )
    action: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        doc="Action verb permitted on the resource.",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Detailed explanation of the capability granted.",
    )

    # Relationships
    roles: Mapped[list["Role"]] = relationship(
        "Role",
        secondary=role_permissions,
        back_populates="permissions",
        lazy="selectin",
    )

    def __init__(
        self,
        *,
        code: str,
        resource: str,
        action: str,
        description: str | None = None,
        id: uuid.UUID | None = None,
        roles: list["Role"] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            code=code,
            resource=resource,
            action=action,
            description=description,
            id=id,
            roles=roles if roles is not None else [],
            **kwargs,
        )

    def __repr__(self) -> str:
        return f"<Permission id={self.id} code='{self.code}' resource='{self.resource}' action='{self.action}'>"
