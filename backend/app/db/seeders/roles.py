"""Enterprise Role and RBAC Matrix Seeder for Investiga.

This module provisions standard enterprise system roles (Super Admin, Admin,
AI Engineer, Investigator, Analyst, Viewer) and binds them to their respective
authorization permissions based on corporate least-privilege security principles.
"""

from typing import TypedDict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.models import Permission, Role
from app.core.logging import get_logger
from app.db.seeders.permissions import seed_permissions

logger = get_logger(__name__)


class RoleSpecification(TypedDict):
    """Specification schema for a platform system role."""

    name: str
    display_name: str
    description: str
    is_system_role: bool
    permission_codes: (
        list[str] | None
    )  # None indicates dynamic wildcard (all permissions)


# ------------------------------------------------------------------------------
# Enterprise Role & Permission Matrix Definitions
# ------------------------------------------------------------------------------
DEFAULT_ROLES: list[RoleSpecification] = [
    # 1. Super Admin: Unrestricted administrative authority
    {
        "name": "super_admin",
        "display_name": "Super Admin",
        "description": "Full platform superuser with unrestricted operational and administrative entitlements.",
        "is_system_role": True,
        "permission_codes": None,  # Dynamically receives all permissions
    },
    # 2. Admin: Platform and User administrator (operational without system root bypass)
    {
        "name": "admin",
        "display_name": "Admin",
        "description": "Operational platform administrator managing users, roles, runbooks, and incidents.",
        "is_system_role": True,
        "permission_codes": [
            "users:view",
            "users:create",
            "users:update",
            "users:delete",
            "roles:view",
            "roles:update",
            "knowledge:view",
            "knowledge:create",
            "knowledge:update",
            "knowledge:delete",
            "documents:upload",
            "documents:update",
            "documents:delete",
            "search:query",
            "investigations:view",
            "investigations:create",
            "investigations:update",
            "investigations:delete",
            "evaluation:view",
            "evaluation:run",
        ],
    },
    # 3. AI Engineer: Knowledge Base, Document Ingestion, Evaluation, and Search specialist
    {
        "name": "ai_engineer",
        "display_name": "AI Engineer",
        "description": "AI operations specialist managing knowledge corpora, embeddings, retrieval pipelines, and evaluations.",
        "is_system_role": True,
        "permission_codes": [
            "knowledge:view",
            "knowledge:create",
            "knowledge:update",
            "knowledge:delete",
            "documents:upload",
            "documents:update",
            "documents:delete",
            "search:query",
            "investigations:view",
            "investigations:create",
            "investigations:update",
            "evaluation:view",
            "evaluation:run",
        ],
    },
    # 4. Investigator: Incident Commander / Lead Investigator executing triage and active investigations
    {
        "name": "investigator",
        "display_name": "Investigator",
        "description": "Incident responder managing active incident investigations, evidence timelines, and queries.",
        "is_system_role": True,
        "permission_codes": [
            "knowledge:view",
            "documents:upload",
            "search:query",
            "investigations:view",
            "investigations:create",
            "investigations:update",
            "evaluation:view",
        ],
    },
    # 5. Analyst: Operational analyst evaluating incidents and viewing knowledge assets
    {
        "name": "analyst",
        "display_name": "Analyst",
        "description": "Operational analyst observing incidents, querying runbooks, and inspecting telemetry.",
        "is_system_role": True,
        "permission_codes": [
            "knowledge:view",
            "search:query",
            "investigations:view",
            "evaluation:view",
        ],
    },
    # 6. Viewer: Read-only stakeholder access
    {
        "name": "viewer",
        "display_name": "Viewer",
        "description": "Read-only auditor with view access to investigations, knowledge articles, and search queries.",
        "is_system_role": True,
        "permission_codes": [
            "knowledge:view",
            "investigations:view",
            "search:query",
        ],
    },
]


async def seed_roles(
    session: AsyncSession,
    permissions_map: dict[str, Permission] | None = None,
) -> dict[str, Role]:
    """Idempotently provision system roles and synchronize role-permission mappings.

    Ensures that default enterprise roles are created and endowed with their assigned
    permissions without generating duplicate records or resetting custom tenant roles.

    Args:
        session: Active asynchronous database transaction session.
        permissions_map: Optional pre-loaded permission dictionary. If None,
                         invokes `seed_permissions()` to guarantee complete inventory.

    Returns:
        dict[str, Role]: Complete mapping of role names to populated Role models.
    """
    # 1. Ensure permissions are seeded
    if permissions_map is None:
        permissions_map = await seed_permissions(session)

    # 2. Fetch all existing roles with permissions in a single round-trip
    stmt = select(Role).options(selectinload(Role.permissions))
    result = await session.execute(stmt)
    existing_roles: dict[str, Role] = {
        role.name: role for role in result.scalars().all()
    }

    new_roles_count = 0
    updated_associations_count = 0

    # 3. Process each role in the enterprise specification
    for spec in DEFAULT_ROLES:
        role_name = spec["name"]

        # Resolve target permissions
        if spec["permission_codes"] is None:
            # Super Admin receives all available permissions
            target_permissions = list(permissions_map.values())
        else:
            target_permissions = [
                permissions_map[code]
                for code in spec["permission_codes"]
                if code in permissions_map
            ]

        if role_name not in existing_roles:
            # Create new role with assigned permissions
            new_role = Role(
                name=role_name,
                display_name=spec["display_name"],
                description=spec["description"],
                is_system_role=spec["is_system_role"],
                permissions=target_permissions,
            )
            session.add(new_role)
            existing_roles[role_name] = new_role
            new_roles_count += 1
            updated_associations_count += len(target_permissions)
        else:
            # Synchronize permissions for existing role to prevent drift
            current_role = existing_roles[role_name]
            existing_perm_codes = {p.code for p in current_role.permissions}
            missing_perms = [
                p for p in target_permissions if p.code not in existing_perm_codes
            ]
            if missing_perms:
                current_role.permissions.extend(missing_perms)
                updated_associations_count += len(missing_perms)

    # 4. Flush changes
    if new_roles_count > 0 or updated_associations_count > 0:
        await session.flush()
        logger.info(
            "roles_seeded",
            new_roles=new_roles_count,
            permission_updates=updated_associations_count,
            total_roles=len(existing_roles),
        )
    else:
        logger.info(
            "roles_seed_skipped",
            reason="all_roles_and_associations_synchronized",
            total_roles=len(existing_roles),
        )

    return existing_roles
