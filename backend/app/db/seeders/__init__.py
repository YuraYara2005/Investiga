"""Database Seeding Infrastructure for Investiga.

This package exposes idempotent asynchronous data seeders for permissions,
system roles, RBAC matrix associations, and initial super administrator accounts.
"""

from app.db.seeders.admin import get_admin_credentials_from_env, seed_admin
from app.db.seeders.permissions import (
    SYSTEM_PERMISSIONS,
    PermissionDefinition,
    seed_permissions,
)
from app.db.seeders.roles import (
    DEFAULT_ROLES,
    RoleSpecification,
    seed_roles,
)
from app.db.seeders.seed import seed_all

__all__ = [
    "DEFAULT_ROLES",
    "SYSTEM_PERMISSIONS",
    "PermissionDefinition",
    "RoleSpecification",
    "get_admin_credentials_from_env",
    "seed_admin",
    "seed_all",
    "seed_permissions",
    "seed_roles",
]
