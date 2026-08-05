"""Identity Domain Models package initialization for Investiga.

Exports User, Role, Permission entities and their association tables.
"""

from app.auth.models.associations import role_permissions, user_roles
from app.auth.models.permission import Permission
from app.auth.models.role import Role
from app.auth.models.user import User

__all__ = [
    "Permission",
    "Role",
    "User",
    "role_permissions",
    "user_roles",
]
