"""Association Tables for Identity Domain RBAC Mappings.

This module defines many-to-many junction tables between Users and Roles,
and between Roles and Permissions, with explicit foreign keys, cascading rules,
and audit tracking timestamps.
"""

from sqlalchemy import Column, DateTime, ForeignKey, Table, func
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base

# Junction table mapping Users to Roles
user_roles = Table(
    "user_roles",
    Base.metadata,
    Column(
        "user_id",
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
        doc="Foreign key reference to the assigned User.",
    ),
    Column(
        "role_id",
        UUID(as_uuid=True),
        ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
        doc="Foreign key reference to the granted Role.",
    ),
    Column(
        "assigned_at",
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        doc="Timestamp in UTC when the role was assigned to the user.",
    ),
    Column(
        "assigned_by",
        UUID(as_uuid=True),
        nullable=True,
        doc="Optional user UUID of the administrator who assigned the role.",
    ),
)

# Junction table mapping Roles to Permissions
role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column(
        "role_id",
        UUID(as_uuid=True),
        ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
        doc="Foreign key reference to the Role.",
    ),
    Column(
        "permission_id",
        UUID(as_uuid=True),
        ForeignKey("permissions.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
        doc="Foreign key reference to the Permission.",
    ),
    Column(
        "granted_at",
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        doc="Timestamp in UTC when the permission was granted to the role.",
    ),
)
