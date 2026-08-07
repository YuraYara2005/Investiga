"""Sync knowledge enum types with application models.

Revision ID: 002_sync_knowledge_enums
Revises: 001_initial_schema
Create Date: 2026-08-06 23:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '002_sync_knowledge_enums'
down_revision: Union[str, None] = '001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Convert columns to varchar temporarily
    op.execute("ALTER TABLE knowledge_documents ALTER COLUMN category TYPE VARCHAR(50)")
    op.execute("ALTER TABLE knowledge_documents ALTER COLUMN processing_status TYPE VARCHAR(50)")
    op.execute("ALTER TABLE knowledge_documents ALTER COLUMN embedding_status TYPE VARCHAR(50)")

    # 2. Map existing legacy values if any
    op.execute("""
        UPDATE knowledge_documents SET
            category = CASE
                WHEN category = 'INCIDENT_POSTMORTEM' THEN 'INCIDENT_REPORT'
                WHEN category = 'STANDARD_OPERATING_PROCEDURE' THEN 'RUNBOOK'
                WHEN category = 'SYSTEM_ARCHITECTURE' THEN 'MANUAL'
                WHEN category = 'SECURITY_POLICY' THEN 'POLICY'
                WHEN category = 'CONFIG_SPECIFICATION' THEN 'CONFIGURATION'
                WHEN category = 'API_DOCUMENTATION' THEN 'MANUAL'
                WHEN category IN ('RUNBOOK', 'INCIDENT_REPORT', 'MANUAL', 'CONFIGURATION', 'POLICY', 'OTHER') THEN category
                ELSE 'OTHER'
            END,
            processing_status = CASE
                WHEN processing_status = 'COMPLETED' THEN 'READY'
                WHEN processing_status IN ('PARSING', 'CHUNKING') THEN 'PROCESSING'
                WHEN processing_status = 'PENDING' THEN 'VALIDATING'
                WHEN processing_status IN ('UPLOADED', 'VALIDATING', 'PROCESSING', 'READY', 'FAILED') THEN processing_status
                ELSE 'FAILED'
            END,
            embedding_status = CASE
                WHEN embedding_status = 'IN_PROGRESS' THEN 'QUEUED'
                WHEN embedding_status IN ('NOT_STARTED', 'QUEUED', 'EMBEDDED', 'FAILED') THEN embedding_status
                ELSE 'FAILED'
            END
    """)

    # 3. Drop old enum types
    op.execute("DROP TYPE IF EXISTS document_category_enum CASCADE")
    op.execute("DROP TYPE IF EXISTS processing_status_enum CASCADE")
    op.execute("DROP TYPE IF EXISTS embedding_status_enum CASCADE")

    # 4. Create new canonical enum types
    document_category_enum = postgresql.ENUM(
        'RUNBOOK', 'INCIDENT_REPORT', 'MANUAL', 'CONFIGURATION', 'POLICY', 'OTHER',
        name='document_category_enum',
    )
    document_category_enum.create(op.get_bind(), checkfirst=True)

    processing_status_enum = postgresql.ENUM(
        'UPLOADED', 'VALIDATING', 'PROCESSING', 'READY', 'FAILED',
        name='processing_status_enum',
    )
    processing_status_enum.create(op.get_bind(), checkfirst=True)

    embedding_status_enum = postgresql.ENUM(
        'NOT_STARTED', 'QUEUED', 'EMBEDDED', 'FAILED',
        name='embedding_status_enum',
    )
    embedding_status_enum.create(op.get_bind(), checkfirst=True)

    # 5. Alter columns back to the new enum types
    op.execute("ALTER TABLE knowledge_documents ALTER COLUMN category TYPE document_category_enum USING category::document_category_enum")
    op.execute("ALTER TABLE knowledge_documents ALTER COLUMN processing_status TYPE processing_status_enum USING processing_status::processing_status_enum")
    op.execute("ALTER TABLE knowledge_documents ALTER COLUMN embedding_status TYPE embedding_status_enum USING embedding_status::embedding_status_enum")


def downgrade() -> None:
    op.execute("ALTER TABLE knowledge_documents ALTER COLUMN category TYPE VARCHAR(50)")
    op.execute("ALTER TABLE knowledge_documents ALTER COLUMN processing_status TYPE VARCHAR(50)")
    op.execute("ALTER TABLE knowledge_documents ALTER COLUMN embedding_status TYPE VARCHAR(50)")

    op.execute("DROP TYPE IF EXISTS document_category_enum CASCADE")
    op.execute("DROP TYPE IF EXISTS processing_status_enum CASCADE")
    op.execute("DROP TYPE IF EXISTS embedding_status_enum CASCADE")

    document_category_enum = postgresql.ENUM(
        'INCIDENT_POSTMORTEM', 'RUNBOOK', 'STANDARD_OPERATING_PROCEDURE',
        'SYSTEM_ARCHITECTURE', 'SECURITY_POLICY', 'CONFIG_SPECIFICATION',
        'API_DOCUMENTATION', 'OTHER',
        name='document_category_enum',
    )
    document_category_enum.create(op.get_bind(), checkfirst=True)

    processing_status_enum = postgresql.ENUM(
        'UPLOADED', 'PENDING', 'PARSING', 'CHUNKING', 'COMPLETED', 'FAILED',
        name='processing_status_enum',
    )
    processing_status_enum.create(op.get_bind(), checkfirst=True)

    embedding_status_enum = postgresql.ENUM(
        'NOT_STARTED', 'IN_PROGRESS', 'EMBEDDED', 'FAILED',
        name='embedding_status_enum',
    )
    embedding_status_enum.create(op.get_bind(), checkfirst=True)

    op.execute("ALTER TABLE knowledge_documents ALTER COLUMN category TYPE document_category_enum USING category::document_category_enum")
    op.execute("ALTER TABLE knowledge_documents ALTER COLUMN processing_status TYPE processing_status_enum USING processing_status::processing_status_enum")
    op.execute("ALTER TABLE knowledge_documents ALTER COLUMN embedding_status TYPE embedding_status_enum USING embedding_status::embedding_status_enum")
