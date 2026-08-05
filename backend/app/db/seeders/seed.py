"""Master Database Seeding Orchestrator for Investiga.

This module provides the central orchestration entry point and CLI runner to
idempotently seed database permissions, roles, and root administrator accounts.
It enforces atomic transaction safety with rollback on failure and guards
production environments from unintended seed runs.

CLI Usage:
    python -m app.db.seeders.seed
    python -m app.db.seeders.seed --force-production
"""

import argparse
import asyncio
import sys
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Permission, Role, User
from app.core.config import get_settings
from app.core.logging import get_logger, setup_logging
from app.db.engine import get_database_engine
from app.db.seeders.admin import seed_admin
from app.db.seeders.permissions import seed_permissions
from app.db.seeders.roles import seed_roles
from app.db.session import get_session_factory

logger = get_logger(__name__)


async def seed_all(
    session: AsyncSession,
    allow_production: bool = False,
) -> dict[str, Any]:
    """Execute complete database seeding orchestration in a single atomic transaction.

    Orchestration sequence:
        1. `seed_permissions()`: Provisions all enterprise capability entitlements.
        2. `seed_roles()`: Provisions standard system roles and assigns permissions.
        3. `seed_admin()`: Provisions the Super Administrator account with Argon2id credentials.

    Args:
        session: Active asynchronous database transaction session.
        allow_production: Safety override to permit seeding in production environments.

    Returns:
        dict[str, Any]: Summary dictionary containing seeded entity counts and metadata.

    Raises:
        RuntimeError: If attempting to run in production without explicit confirmation.
        Exception: If any seeding step fails, triggering an automatic rollback.
    """
    settings = get_settings()

    # 1. Production safety guard
    if settings.app.is_production and not allow_production:
        error_msg = (
            "Automatic database seeding is strictly blocked in production environments. "
            "Pass `allow_production=True` or use CLI `--force-production` to execute."
        )
        logger.error("seeder_production_guard_triggered", message=error_msg)
        raise RuntimeError(error_msg)

    logger.info(
        "database_seeding_started",
        environment=settings.app.environment,
        app_name=settings.app.name,
    )

    try:
        # Step 1: Seed system permissions
        permissions_map: dict[str, Permission] = await seed_permissions(session)

        # Step 2: Seed system roles and bind permission matrix
        roles_map: dict[str, Role] = await seed_roles(
            session, permissions_map=permissions_map
        )

        # Step 3: Seed Super Administrator principal
        admin_user: User = await seed_admin(session, roles_map=roles_map)

        # Step 4: Commit entire atomic transaction
        await session.commit()

        summary = {
            "permissions_count": len(permissions_map),
            "roles_count": len(roles_map),
            "admin_email": admin_user.email,
            "admin_id": str(admin_user.id),
            "status": "success",
        }

        logger.info("database_seeding_completed", **summary)
        return summary

    except Exception as exc:
        await session.rollback()
        logger.error(
            "database_seeding_failed",
            error=str(exc),
            exc_info=True,
        )
        raise


async def run_cli() -> None:
    """CLI runner executing seeding orchestration from terminal commands."""
    setup_logging()

    parser = argparse.ArgumentParser(
        description="Investiga Master Database Seeder CLI",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--force-production",
        action="store_true",
        default=False,
        help="Explicitly allow seeding to execute in production environment.",
    )
    args = parser.parse_args()

    session_maker = get_session_factory()

    try:
        async with session_maker() as session:
            summary = await seed_all(
                session=session,
                allow_production=args.force_production,
            )
            print("\n==================================================")
            print("  Investiga Database Seeding Completed Successfully")
            print("==================================================")
            print(f"  * Permissions Active: {summary['permissions_count']}")
            print(f"  * Roles Active:       {summary['roles_count']}")
            print(
                f"  * Admin Principal:    {summary['admin_email']} ({summary['admin_id']})"
            )
            print("==================================================\n")
    except Exception as err:
        print(f"\n[ERROR] Database seeding failed: {err}", file=sys.stderr)
        sys.exit(1)
    finally:
        engine = get_database_engine()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run_cli())
