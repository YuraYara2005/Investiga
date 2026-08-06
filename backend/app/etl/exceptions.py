"""ETL Subsystem Domain Exceptions for Investiga.

Provides standardized exception hierarchies for loader discovery, configuration validation,
pipeline execution, cancellation, and scheduler coordination.
"""

from __future__ import annotations

import uuid
from typing import Any

from app.exceptions.base import BaseAppException


class ETLException(BaseAppException):
    """Base exception for all ETL domain errors."""

    def __init__(
        self,
        message: str,
        job_id: uuid.UUID | str | None = None,
        source: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        merged_details: dict[str, Any] = details or {}
        if job_id is not None:
            merged_details["job_id"] = str(job_id)
        if source is not None:
            merged_details["source"] = source

        super().__init__(
            message=message,
            status_code=500,
            error_code="ETL_ERROR",
            details=merged_details,
        )


class ETLValidationException(ETLException):
    """Raised when ETL configuration or source parameters fail validation."""

    def __init__(
        self,
        message: str,
        job_id: uuid.UUID | str | None = None,
        source: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message=message, job_id=job_id, source=source, details=details)
        self.status_code = 422
        self.error_code = "ETL_VALIDATION_ERROR"


class ETLLoaderException(ETLException):
    """Base exception for data loader discovery and extraction failures."""

    def __init__(
        self,
        message: str,
        source: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message=message, source=source, details=details)
        self.status_code = 502
        self.error_code = "ETL_LOADER_ERROR"


class ETLDiscoveryException(ETLLoaderException):
    """Raised when discovering items from an external source fails."""

    def __init__(
        self,
        message: str,
        source: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message=message, source=source, details=details)
        self.error_code = "ETL_DISCOVERY_ERROR"


class ETLLoadException(ETLLoaderException):
    """Raised when loading content payload from a discovered source item fails."""

    def __init__(
        self,
        message: str,
        source_uri: str | None = None,
        source: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        merged_details = details or {}
        if source_uri:
            merged_details["source_uri"] = source_uri
        super().__init__(message=message, source=source, details=merged_details)
        self.error_code = "ETL_LOAD_ERROR"


class ETLPipelineException(ETLException):
    """Raised when pipeline orchestration fails."""

    def __init__(
        self,
        message: str,
        job_id: uuid.UUID | str | None = None,
        stage: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        merged_details = details or {}
        if stage is not None:
            merged_details["stage"] = stage
        super().__init__(message=message, job_id=job_id, details=merged_details)
        self.error_code = "ETL_PIPELINE_ERROR"


class ETLJobNotFoundException(ETLException):
    """Raised when referencing a non-existent ETL job ID."""

    def __init__(
        self,
        job_id: uuid.UUID | str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=f"ETL Job with ID '{job_id}' was not found.",
            job_id=job_id,
            details=details,
        )
        self.status_code = 404
        self.error_code = "ETL_JOB_NOT_FOUND"


class ETLJobCancelledException(ETLException):
    """Raised when an ETL job execution is halted by cancellation request."""

    def __init__(
        self,
        job_id: uuid.UUID | str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        message = (
            f"ETL Job '{job_id}' was cancelled by user request."
            if job_id is not None
            else "ETL Job was cancelled by user request."
        )
        super().__init__(
            message=message,
            job_id=job_id,
            details=details,
        )
        self.status_code = 409
        self.error_code = "ETL_JOB_CANCELLED"


class ETLJobExecutionException(ETLException):
    """Raised when an unrecoverable runtime error occurs during ETL job execution."""

    def __init__(
        self,
        message: str,
        job_id: uuid.UUID | str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message=message, job_id=job_id, details=details)
        self.error_code = "ETL_JOB_EXECUTION_ERROR"


class ETLUnsupportedSourceException(ETLException):
    """Raised when requesting a loader or source type that is unregistered or unsupported."""

    def __init__(
        self,
        source: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=f"ETL source type '{source}' is not supported or not implemented.",
            source=source,
            details=details,
        )
        self.status_code = 400
        self.error_code = "ETL_UNSUPPORTED_SOURCE"
