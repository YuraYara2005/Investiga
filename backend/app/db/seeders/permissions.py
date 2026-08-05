"""Enterprise Permission Seeder for Investiga.

This module defines and idempotently provisions the foundational authorization
entitlements (resource:action namespaces) required across all platform domains:
User Administration, RBAC, Knowledge Management, Ingestion, Hybrid Search,
Incident Investigations, LLM Evaluation, and System Administration.
"""

from typing import TypedDict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Permission
from app.core.logging import get_logger

logger = get_logger(__name__)


class PermissionDefinition(TypedDict):
    """Specification schema for a platform permission entitlement."""

    code: str
    resource: str
    action: str
    description: str


SYSTEM_PERMISSIONS: list[PermissionDefinition] = [
    # --------------------------------------------------------------------------
    # User Management Namespace
    # --------------------------------------------------------------------------
    {
        "code": "users:view",
        "resource": "users",
        "action": "view",
        "description": "View user accounts, metadata, and directory listings.",
    },
    {
        "code": "users:create",
        "resource": "users",
        "action": "create",
        "description": "Provision new user accounts and onboarding invitations.",
    },
    {
        "code": "users:update",
        "resource": "users",
        "action": "update",
        "description": "Modify user account profiles, states, and credentials.",
    },
    {
        "code": "users:delete",
        "resource": "users",
        "action": "delete",
        "description": "Deactivate or soft-delete user accounts.",
    },
    # --------------------------------------------------------------------------
    # Role-Based Access Control (RBAC) Namespace
    # --------------------------------------------------------------------------
    {
        "code": "roles:view",
        "resource": "roles",
        "action": "view",
        "description": "View system roles, hierarchies, and permission grants.",
    },
    {
        "code": "roles:update",
        "resource": "roles",
        "action": "update",
        "description": "Assign or revoke roles and modify permission mappings.",
    },
    # --------------------------------------------------------------------------
    # Knowledge Base & Document Management Namespace
    # --------------------------------------------------------------------------
    {
        "code": "knowledge:view",
        "resource": "knowledge",
        "action": "view",
        "description": "Read knowledge collections, runbooks, and curated notes.",
    },
    {
        "code": "knowledge:create",
        "resource": "knowledge",
        "action": "create",
        "description": "Author new knowledge articles and post-mortem runbooks.",
    },
    {
        "code": "knowledge:update",
        "resource": "knowledge",
        "action": "update",
        "description": "Update knowledge content and categorization metadata.",
    },
    {
        "code": "knowledge:delete",
        "resource": "knowledge",
        "action": "delete",
        "description": "Archive or remove knowledge base documents.",
    },
    {
        "code": "documents:upload",
        "resource": "documents",
        "action": "upload",
        "description": "Upload raw incident logs, telemetry dumps, and attachments.",
    },
    {
        "code": "documents:update",
        "resource": "documents",
        "action": "update",
        "description": "Modify document tags, indexing configurations, and metadata.",
    },
    {
        "code": "documents:delete",
        "resource": "documents",
        "action": "delete",
        "description": "Purge ingested operational documents and indices.",
    },
    # --------------------------------------------------------------------------
    # Hybrid Search & Retrieval Namespace
    # --------------------------------------------------------------------------
    {
        "code": "search:query",
        "resource": "search",
        "action": "query",
        "description": "Execute semantic, BM25 keyword, and hybrid vector search queries.",
    },
    # --------------------------------------------------------------------------
    # Incident Investigations & Reasoning Namespace
    # --------------------------------------------------------------------------
    {
        "code": "investigations:view",
        "resource": "investigations",
        "action": "view",
        "description": "Inspect active and historical incident investigations and graphs.",
    },
    {
        "code": "investigations:create",
        "resource": "investigations",
        "action": "create",
        "description": "Initiate new incident investigations and diagnostic sessions.",
    },
    {
        "code": "investigations:update",
        "resource": "investigations",
        "action": "update",
        "description": "Append incident evidence, update timelines, and edit hypotheses.",
    },
    {
        "code": "investigations:delete",
        "resource": "investigations",
        "action": "delete",
        "description": "Close, archive, or delete incident investigation records.",
    },
    # --------------------------------------------------------------------------
    # RAG & LLM Evaluation Namespace
    # --------------------------------------------------------------------------
    {
        "code": "evaluation:view",
        "resource": "evaluation",
        "action": "view",
        "description": "View LLM reasoning evaluations, faithfulness, and answer relevance telemetry.",
    },
    {
        "code": "evaluation:run",
        "resource": "evaluation",
        "action": "run",
        "description": "Trigger automated RAG benchmark evaluation suites.",
    },
    # --------------------------------------------------------------------------
    # System Administration Super-Entitlement
    # --------------------------------------------------------------------------
    {
        "code": "system:admin",
        "resource": "system",
        "action": "admin",
        "description": "Unrestricted administrative control across platform infrastructure.",
    },
]


async def seed_permissions(session: AsyncSession) -> dict[str, Permission]:
    """Idempotently seed foundational system permissions into the database.

    Fetches existing permissions in a single round-trip, computes the difference,
    and inserts missing entities without generating duplicate key collisions.

    Args:
        session: Active asynchronous database transaction session.

    Returns:
        dict[str, Permission]: Complete mapping of permission codes to Permission models.
    """
    # 1. Fetch all existing permissions in a single query
    stmt = select(Permission)
    result = await session.execute(stmt)
    existing_permissions: dict[str, Permission] = {
        perm.code: perm for perm in result.scalars().all()
    }

    # 2. Identify missing permissions
    new_permissions: list[Permission] = []
    for spec in SYSTEM_PERMISSIONS:
        if spec["code"] not in existing_permissions:
            new_perm = Permission(
                code=spec["code"],
                resource=spec["resource"],
                action=spec["action"],
                description=spec["description"],
            )
            session.add(new_perm)
            new_permissions.append(new_perm)

    # 3. Persist and flush if any new permissions were identified
    if new_permissions:
        await session.flush()
        for perm in new_permissions:
            existing_permissions[perm.code] = perm

        logger.info(
            "permissions_seeded",
            new_count=len(new_permissions),
            total_count=len(existing_permissions),
        )
    else:
        logger.info(
            "permissions_seed_skipped",
            reason="all_permissions_exist",
            total_count=len(existing_permissions),
        )

    return existing_permissions
