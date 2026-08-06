"""ETL Subsystem Abstract Interfaces for Investiga.

Defines protocol contracts for data loaders, pipeline execution engines,
loader registries, and job schedulers following Clean Architecture principles.
"""

from __future__ import annotations

import asyncio
import uuid
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.etl.models import (
    ETLConfiguration,
    ETLDiscoveredItem,
    ETLDocumentStreamItem,
    ETLJob,
    ETLResult,
    ETLSource,
)


class BaseLoaderInterface(ABC):
    """Abstract interface defining the mandatory contract for all ETL data loaders."""

    @abstractmethod
    def discover(
        self,
        config: ETLConfiguration,
    ) -> AsyncIterator[ETLDiscoveredItem]:
        """Asynchronously discover candidate documents matching configuration rules.

        Args:
            config: Job configuration containing source URI and filter patterns.

        Yields:
            ETLDiscoveredItem: Discovered item metadata prior to content download.
        """
        ...

    @abstractmethod
    async def load(
        self,
        item: ETLDiscoveredItem,
        config: ETLConfiguration,
    ) -> ETLDocumentStreamItem:
        """Asynchronously load and materialize a discovered item into a document stream.

        Args:
            item: Discovered item metadata.
            config: Job configuration.

        Returns:
            ETLDocumentStreamItem: Materialized payload with byte contents and metadata.
        """
        ...

    @abstractmethod
    def supports(self, source_type: ETLSource | str) -> bool:
        """Evaluate whether this loader implementation supports the given source type.

        Args:
            source_type: ETLSource enum or string identifier.

        Returns:
            bool: True if source type is handled by this loader.
        """
        ...

    @abstractmethod
    def validate(self, config: ETLConfiguration) -> bool:
        """Validate whether the supplied configuration is valid and reachable for this loader.

        Args:
            config: Job configuration to validate.

        Returns:
            bool: True if configuration is valid.

        Raises:
            ETLValidationException: If configuration parameters are invalid.
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Verify the health, network reachability, and availability of the underlying source.

        Returns:
            bool: True if source service/filesystem is healthy.
        """
        ...


class ETLPipelineInterface(ABC):
    """Abstract interface for the ETL pipeline orchestration engine."""

    @abstractmethod
    async def execute(
        self,
        job: ETLJob,
        session: AsyncSession,
        cancellation_token: asyncio.Event | None = None,
    ) -> ETLResult:
        """Execute an end-to-end ETL job through the ingestion and vectorization pipeline.

        Args:
            job: ETL job record containing configuration and checkpoint state.
            session: Active database session.
            cancellation_token: Optional event flag for graceful job cancellation.

        Returns:
            ETLResult: Complete summary and metrics of the ingestion run.
        """
        ...


class ETLRegistryInterface(ABC):
    """Abstract contract for registering and resolving ETL data loader instances."""

    @abstractmethod
    def register(
        self,
        source: ETLSource,
        loader: BaseLoaderInterface,
    ) -> None:
        """Register a loader instance for an ETL source type."""
        ...

    @abstractmethod
    def get(self, source: ETLSource | str) -> BaseLoaderInterface:
        """Retrieve a loader registered for the given source type."""
        ...


class ETLSchedulerInterface(ABC):
    """Abstract contract for scheduling and triggering recurrent or manual ETL sync jobs."""

    @abstractmethod
    def schedule_job(
        self,
        job_id: uuid.UUID,
        schedule_type: str,
        run_fn: Any,
        **kwargs: Any,
    ) -> str:
        """Register a schedule for an ETL job."""
        ...

    @abstractmethod
    def cancel_schedule(self, schedule_id: str) -> bool:
        """Cancel an active scheduled sync job."""
        ...
