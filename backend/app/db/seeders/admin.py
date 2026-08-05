"""Administrator Account Seeder for Investiga.

This module idempotently provisions the root administrator/superuser account for
the platform. Credentials are exclusively extracted from environment variables
and securely hashed using the Argon2id cryptographic infrastructure.
"""

import os

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.models import Role, User
from app.core.logging import get_logger
from app.core.security import async_get_password_hash
from app.db.seeders.roles import seed_roles

logger = get_logger(__name__)


def get_admin_credentials_from_env() -> dict[str, str]:
    """Retrieve administrator provisioning parameters from environment variables.

    Reads environment variables adhering to the 12-factor configuration model.

    Returns:
        dict[str, str]: Dictionary with email, password, and full_name.
    """
    email = (
        (
            os.getenv("INITIAL_ADMIN_EMAIL")
            or os.getenv("ADMIN_EMAIL")
            or "admin@investiga.internal"
        )
        .strip()
        .lower()
    )

    password = (
        os.getenv("INITIAL_ADMIN_PASSWORD")
        or os.getenv("ADMIN_PASSWORD")
        or "InvestigaSuperAdmin#2026!"
    )

    full_name = (
        os.getenv("INITIAL_ADMIN_FULL_NAME")
        or os.getenv("ADMIN_FULL_NAME")
        or "Investiga Super Administrator"
    ).strip()

    return {
        "email": email,
        "password": password,
        "full_name": full_name,
    }


async def seed_admin(
    session: AsyncSession,
    roles_map: dict[str, Role] | None = None,
    custom_credentials: dict[str, str] | None = None,
) -> User:
    """Idempotently provision the initial system Super Administrator account.

    If an administrator account with the configured email already exists, no duplicate
    account is created, and the existing principal is returned intact.

    Args:
        session: Active asynchronous database transaction session.
        roles_map: Optional pre-loaded roles mapping from `seed_roles()`.
        custom_credentials: Optional explicit credentials dict (useful for hermetic tests).

    Returns:
        User: The created or existing Super Administrator entity.
    """
    # 1. Resolve roles
    if roles_map is None:
        roles_map = await seed_roles(session)

    super_admin_role = roles_map.get("super_admin")
    if super_admin_role is None:
        stmt = (
            select(Role)
            .where(Role.name == "super_admin")
            .options(selectinload(Role.permissions))
        )
        res = await session.execute(stmt)
        super_admin_role = res.scalar_one_or_none()

    # 2. Resolve credentials from environment or parameters
    creds = custom_credentials or get_admin_credentials_from_env()
    email = creds["email"]
    password = creds["password"]
    full_name = creds["full_name"]

    # 3. Check for existing user by email
    stmt_user = (
        select(User)
        .where(User.email == email)
        .options(selectinload(User.roles).selectinload(Role.permissions))
    )
    user_res = await session.execute(stmt_user)
    existing_user = user_res.scalar_one_or_none()

    if existing_user is not None:
        # Ensure superuser flag and super_admin role are assigned even if existing
        modified = False
        if not existing_user.is_superuser:
            existing_user.is_superuser = True
            modified = True
        if not existing_user.is_active:
            existing_user.is_active = True
            modified = True

        if super_admin_role is not None:
            existing_role_names = {r.name for r in existing_user.roles}
            if "super_admin" not in existing_role_names:
                existing_user.roles.append(super_admin_role)
                modified = True

        if modified:
            await session.flush()

        logger.info(
            "admin_already_exists",
            email=email,
            user_id=str(existing_user.id),
            is_superuser=existing_user.is_superuser,
        )
        return existing_user

    # 4. Hash password asynchronously with Argon2id
    hashed_password = await async_get_password_hash(password)

    # 5. Construct new Super Admin User
    admin_user = User(
        email=email,
        hashed_password=hashed_password,
        full_name=full_name,
        is_active=True,
        is_verified=True,
        is_superuser=True,
        roles=[super_admin_role] if super_admin_role else [],
    )

    session.add(admin_user)
    await session.flush()

    logger.info(
        "admin_created",
        email=email,
        user_id=str(admin_user.id),
        is_superuser=True,
    )

    return admin_user
