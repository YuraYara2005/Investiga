"""User Repository for Identity Management in Investiga.

This module provides specialized database query routines for User entities,
including eager loading of roles/permissions (`selectinload`), email lookups,
audit updates, and paginated searches without N+1 query overhead.
"""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import func, or_, select
from sqlalchemy import update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.models import Role, User
from app.auth.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """Repository handling persistence operations and optimized queries for Users."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session=session, model_cls=User)

    async def get_by_email(
        self, email: str, include_deleted: bool = False
    ) -> User | None:
        """Retrieve a user by their unique canonical email address.

        Args:
            email: Canonical user email string.
            include_deleted: Whether to consider soft-deleted records.

        Returns:
            User | None: The matching user entity or None.
        """
        stmt = select(User).where(func.lower(User.email) == email.strip().lower())
        if not include_deleted:
            stmt = stmt.where(User.is_deleted.is_(False))

        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def email_exists(self, email: str) -> bool:
        """Check if an active account is already registered with the specified email.

        Args:
            email: Email address string to verify.

        Returns:
            bool: True if email is already taken by an active user.
        """
        stmt = (
            select(func.count())
            .select_from(User)
            .where(func.lower(User.email) == email.strip().lower())
            .where(User.is_deleted.is_(False))
        )
        result = await self._session.execute(stmt)
        return result.scalar_one() > 0

    async def get_with_roles(
        self, user_id: uuid.UUID, include_deleted: bool = False
    ) -> User | None:
        """Fetch a user and eagerly load their assigned roles using selectinload.

        Args:
            user_id: User UUID.
            include_deleted: Whether to consider soft-deleted records.

        Returns:
            User | None: User entity with loaded `roles` collection.
        """
        stmt = (
            select(User)
            .where(User.id == user_id)
            .options(selectinload(User.roles))
        )
        if not include_deleted:
            stmt = stmt.where(User.is_deleted.is_(False))

        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_with_roles_and_permissions(
        self, user_id: uuid.UUID, include_deleted: bool = False
    ) -> User | None:
        """Fetch a user with deep eager loading of both roles and granular permissions.

        Args:
            user_id: User UUID.
            include_deleted: Whether to consider soft-deleted records.

        Returns:
            User | None: User entity with fully populated roles and permissions graph.
        """
        stmt = (
            select(User)
            .where(User.id == user_id)
            .options(
                selectinload(User.roles).selectinload(Role.permissions)
            )
        )
        if not include_deleted:
            stmt = stmt.where(User.is_deleted.is_(False))

        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_email_with_roles_and_permissions(
        self, email: str, include_deleted: bool = False
    ) -> User | None:
        """Optimized query for authentication: resolves user, roles, and permissions in one step.

        Eliminates N+1 query bottlenecks during high-throughput login authorization.

        Args:
            email: Canonical user email.
            include_deleted: Whether to consider soft-deleted records.

        Returns:
            User | None: Fully hydrated User entity or None.
        """
        stmt = (
            select(User)
            .where(func.lower(User.email) == email.strip().lower())
            .options(
                selectinload(User.roles).selectinload(Role.permissions)
            )
        )
        if not include_deleted:
            stmt = stmt.where(User.is_deleted.is_(False))

        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_last_login(self, user_id: uuid.UUID) -> None:
        """Update the last_login_at audit timestamp for a user without reloading the full entity.

        Args:
            user_id: User UUID.
        """
        stmt = (
            sa_update(User)
            .where(User.id == user_id)
            .values(last_login_at=datetime.now(UTC))
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def search_users(
        self,
        query: str | None = None,
        is_active: bool | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[Sequence[User], int]:
        """Search and paginate user records with multi-field filtering and total count.

        Args:
            query: Optional search keyword matched against email and full_name.
            is_active: Optional boolean filter for active status.
            skip: Pagination offset.
            limit: Maximum items per page.

        Returns:
            tuple[Sequence[User], int]: Tuple containing the list of users and total count.
        """
        base_stmt = select(User).where(User.is_deleted.is_(False))
        count_stmt = select(func.count()).select_from(User).where(User.is_deleted.is_(False))

        if query:
            search_filter = or_(
                User.email.ilike(f"%{query.strip()}%"),
                User.full_name.ilike(f"%{query.strip()}%"),
            )
            base_stmt = base_stmt.where(search_filter)
            count_stmt = count_stmt.where(search_filter)

        if is_active is not None:
            base_stmt = base_stmt.where(User.is_active == is_active)
            count_stmt = count_stmt.where(User.is_active == is_active)

        # Count total matches
        total_result = await self._session.execute(count_stmt)
        total_count = total_result.scalar_one()

        # Fetch paginated slice with roles eagerly loaded
        data_stmt = (
            base_stmt.options(selectinload(User.roles))
            .order_by(User.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        data_result = await self._session.execute(data_stmt)
        users = data_result.scalars().all()

        return users, total_count
