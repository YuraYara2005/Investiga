"""Repository Interface Protocols for the Identity Domain.

This module defines formal abstract protocols for Identity data access components,
adhering to the Dependency Inversion Principle (DIP) of Clean Architecture.
Business services depend on these interfaces rather than concrete SQLAlchemy implementations.
"""

import uuid
from collections.abc import Sequence
from typing import Generic, Protocol, TypeVar

from app.auth.models import Permission, Role, User
from app.db.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class IBaseRepository(Protocol, Generic[ModelType]):
    """Generic repository protocol defining standard asynchronous CRUD operations."""

    async def create(self, entity: ModelType) -> ModelType: ...

    async def get_by_id(
        self, entity_id: uuid.UUID, include_deleted: bool = False
    ) -> ModelType | None: ...

    async def get_all(
        self, skip: int = 0, limit: int = 100, include_deleted: bool = False
    ) -> Sequence[ModelType]: ...

    async def update(self, entity: ModelType) -> ModelType: ...

    async def delete(self, entity_id: uuid.UUID, hard_delete: bool = False) -> bool: ...

    async def exists(self, entity_id: uuid.UUID) -> bool: ...

    async def count(self, include_deleted: bool = False) -> int: ...


class IUserRepository(IBaseRepository[User], Protocol):
    """Repository protocol specialized for User identity lifecycle and credential queries."""

    async def get_by_email(
        self, email: str, include_deleted: bool = False
    ) -> User | None: ...

    async def email_exists(self, email: str) -> bool: ...

    async def get_with_roles(
        self, user_id: uuid.UUID, include_deleted: bool = False
    ) -> User | None: ...

    async def get_with_roles_and_permissions(
        self, user_id: uuid.UUID, include_deleted: bool = False
    ) -> User | None: ...

    async def get_by_email_with_roles_and_permissions(
        self, email: str, include_deleted: bool = False
    ) -> User | None: ...

    async def update_last_login(self, user_id: uuid.UUID) -> None: ...

    async def search_users(
        self,
        query: str | None = None,
        is_active: bool | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[Sequence[User], int]: ...


class IRoleRepository(IBaseRepository[Role], Protocol):
    """Repository protocol specialized for RBAC Role entity management."""

    async def get_by_name(
        self, name: str, include_deleted: bool = False
    ) -> Role | None: ...

    async def get_system_roles(self) -> Sequence[Role]: ...

    async def get_with_permissions(
        self, role_id: uuid.UUID, include_deleted: bool = False
    ) -> Role | None: ...

    async def assign_permission(
        self, role: Role, permission: Permission
    ) -> None: ...

    async def remove_permission(
        self, role: Role, permission: Permission
    ) -> None: ...


class IPermissionRepository(IBaseRepository[Permission], Protocol):
    """Repository protocol specialized for operational entitlement permissions."""

    async def get_by_code(self, code: str) -> Permission | None: ...

    async def get_by_resource(self, resource: str) -> Sequence[Permission]: ...

    async def permission_exists(self, code: str) -> bool: ...

    async def bulk_create(
        self, permissions: list[Permission]
    ) -> Sequence[Permission]: ...
