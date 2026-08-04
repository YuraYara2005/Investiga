"""SQLAlchemy metadata naming conventions for Investiga.

This module defines deterministic constraint naming conventions for SQLAlchemy
metadata. Explicitly naming primary keys, foreign keys, unique constraints,
check constraints, and indexes is a mandatory enterprise best practice that
enables Alembic to perform reliable, reversible, and non-ambiguous schema migrations.
"""

from typing import Final

# Standardized constraint naming convention dictionary for SQLAlchemy MetaData.
# Without explicit naming conventions, relational databases assign auto-generated
# anonymous names to constraints, which breaks automated Alembic migration scripts
# (e.g. op.drop_constraint) across different database environments.
CONSTRAINT_NAMING_CONVENTIONS: Final[dict[str, str]] = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}
