"""Permission Repository for Authorization Entitlements in Investiga.

This module provides data access routines for atomic Permission entities.
"""

from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Permission
from app.auth.repositories.base import BaseRepository


class PermissionRepository(BaseRepository[Permission]):
    """Repository handling persistence operations for Permission entities."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session=session, model_cls=Permission)

    async def get_by_code(self, code: str) -> Permission | None:
        """Retrieve a permission entity by its canonical identifier string.

        Args:
            code: Unique permission code string (e.g., 'investigations:create').

        Returns:
            Permission | None: The matching permission entity or None.
        """
        stmt = select(Permission).where(Permission.code == code.strip())
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_resource(self, resource: str) -> Sequence[Permission]:
        """Retrieve all permissions defined under a specific resource namespace.

        Args:
            resource: Resource namespace string (e.g., 'investigations', 'knowledge').

        Returns:
            Sequence[Permission]: List of matching permissions.
        """
        stmt = (
            select(Permission)
            .where(Permission.resource == resource.strip().lower())
            .order_by(Permission.code.asc())
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def permission_exists(self, code: str) -> bool:
        """Check whether a permission with the given code already exists.

        Args:
            code: Permission code to verify.

        Returns:
            bool: True if permission exists, False otherwise.
        """
        stmt = (
            select(func.count())
            .select_from(Permission)
            .where(Permission.code == code.strip())
        )
        result = await self._session.execute(stmt)
        return result.scalar_one() > 0

    async def bulk_create(
        self, permissions: list[Permission]
    ) -> Sequence[Permission]:
        """Persist a batch of permission entities during system initialization or seeding.

        Args:
            permissions: List of Permission model instances.

        Returns:
            Sequence[Permission]: Persisted and refreshed permissions.
        """
        self._session.add_all(permissions)
        await self._session.flush()
        for perm in permissions:
            await self._session.refresh(perm)
        return permissions
