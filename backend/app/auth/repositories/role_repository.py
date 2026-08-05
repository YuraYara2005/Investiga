"""Role Repository for Role-Based Access Control in Investiga.

This module encapsulates persistence queries and relationship mutations for
Role domain entities and their assigned permissions.
"""

import uuid
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.models import Permission, Role
from app.auth.repositories.base import BaseRepository


class RoleRepository(BaseRepository[Role]):
    """Repository handling persistence operations and RBAC management for Roles."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session=session, model_cls=Role)

    async def get_by_name(
        self, name: str, include_deleted: bool = False
    ) -> Role | None:
        """Retrieve a role by its unique canonical name (e.g. 'admin', 'investigator').

        Args:
            name: Canonical role key string.
            include_deleted: Whether to consider soft-deleted records.

        Returns:
            Role | None: The matching role entity or None.
        """
        stmt = select(Role).where(func.lower(Role.name) == name.strip().lower())
        if not include_deleted:
            stmt = stmt.where(Role.is_deleted.is_(False))

        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_system_roles(self) -> Sequence[Role]:
        """Retrieve all immutable built-in platform system roles.

        Returns:
            Sequence[Role]: List of active system roles.
        """
        stmt = (
            select(Role)
            .where(Role.is_system_role.is_(True))
            .where(Role.is_deleted.is_(False))
            .order_by(Role.name.asc())
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_with_permissions(
        self, role_id: uuid.UUID, include_deleted: bool = False
    ) -> Role | None:
        """Retrieve a role with its assigned permissions eagerly loaded.

        Args:
            role_id: Role UUID.
            include_deleted: Whether to consider soft-deleted records.

        Returns:
            Role | None: Role entity with populated permissions collection.
        """
        stmt = (
            select(Role)
            .where(Role.id == role_id)
            .options(selectinload(Role.permissions))
        )
        if not include_deleted:
            stmt = stmt.where(Role.is_deleted.is_(False))

        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def assign_permission(self, role: Role, permission: Permission) -> None:
        """Associate an operational permission entitlement with a role.

        Args:
            role: The target role entity.
            permission: The permission entity to grant.
        """
        if permission not in role.permissions:
            role.permissions.append(permission)
            await self._session.flush()

    async def remove_permission(self, role: Role, permission: Permission) -> None:
        """Revoke a permission entitlement from a role.

        Args:
            role: The target role entity.
            permission: The permission entity to revoke.
        """
        if permission in role.permissions:
            role.permissions.remove(permission)
            await self._session.flush()
