"""Enumeration Definitions for Knowledge Management in Investiga.

This module defines standard enumeration types for document categorization,
ingestion processing lifecycles, and embedding vector indexing states.
"""

from enum import StrEnum


class DocumentCategory(StrEnum):
    """Business categorization domain for operational knowledge assets."""

    RUNBOOK = "RUNBOOK"
    INCIDENT_REPORT = "INCIDENT_REPORT"
    MANUAL = "MANUAL"
    CONFIGURATION = "CONFIGURATION"
    POLICY = "POLICY"
    OTHER = "OTHER"


class ProcessingStatus(StrEnum):
    """Pipeline lifecycle state for ingested document files."""

    UPLOADED = "UPLOADED"
    VALIDATING = "VALIDATING"
    PROCESSING = "PROCESSING"
    READY = "READY"
    FAILED = "FAILED"


class EmbeddingStatus(StrEnum):
    """Vector database embedding and chunk indexing synchronization status."""

    NOT_STARTED = "NOT_STARTED"
    QUEUED = "QUEUED"
    EMBEDDED = "EMBEDDED"
    FAILED = "FAILED"
