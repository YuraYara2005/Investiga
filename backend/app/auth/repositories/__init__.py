"""Repositories package initialization for the Identity Domain.

Exports repository implementations and protocols.
"""

from app.auth.repositories.base import BaseRepository
from app.auth.repositories.interfaces import (
    IBaseRepository,
    IPermissionRepository,
    IRoleRepository,
    IUserRepository,
)
from app.auth.repositories.permission_repository import PermissionRepository
from app.auth.repositories.role_repository import RoleRepository
from app.auth.repositories.user_repository import UserRepository

__all__ = [
    "BaseRepository",
    "IBaseRepository",
    "IPermissionRepository",
    "IRoleRepository",
    "IUserRepository",
    "PermissionRepository",
    "RoleRepository",
    "UserRepository",
]
