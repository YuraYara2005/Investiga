"""Lightweight ETL Scheduler Abstraction for Investiga.

Provides job scheduling representations and metadata management for manual, hourly,
and daily recurring synchronization workflows.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.etl.interfaces import ETLSchedulerInterface

logger = get_logger(__name__)


class ScheduleFrequency(StrEnum):
    """Supported execution recurrence patterns."""

    MANUAL = "manual"
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    CUSTOM = "custom"


class ScheduledETLEntry(BaseModel):
    """Record representing a scheduled recurring ETL task."""

    schedule_id: str = Field(
        default_factory=lambda: uuid.uuid4().hex[:12],
        description="Unique identifier for schedule entry.",
    )
    job_id: uuid.UUID = Field(
        ...,
        description="Target ETL job identifier.",
    )
    frequency: ScheduleFrequency = Field(
        ...,
        description="Recurrence frequency.",
    )
    is_active: bool = Field(
        default=True,
        description="Whether this schedule is currently enabled.",
    )
    cron_expression: str | None = Field(
        default=None,
        description="Optional custom cron syntax expression.",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Creation timestamp.",
    )
    last_run_at: datetime | None = Field(
        default=None,
        description="Last execution timestamp.",
    )
    next_run_at: datetime | None = Field(
        default=None,
        description="Calculated next execution timestamp.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Schedule metadata and parameters.",
    )

    def calculate_next_run(self) -> datetime:
        """Compute the next scheduled execution timestamp."""
        now = datetime.now(UTC)
        if self.frequency == ScheduleFrequency.HOURLY:
            self.next_run_at = now + timedelta(hours=1)
        elif self.frequency == ScheduleFrequency.DAILY:
            self.next_run_at = now + timedelta(days=1)
        elif self.frequency == ScheduleFrequency.WEEKLY:
            self.next_run_at = now + timedelta(weeks=1)
        else:
            self.next_run_at = None
        return self.next_run_at or now


class ETLScheduler(ETLSchedulerInterface):
    """In-memory scheduler abstraction for recurring and manual ETL sync jobs."""

    def __init__(self) -> None:
        """Initialize scheduler storage."""
        self._schedules: dict[str, ScheduledETLEntry] = {}

    def schedule_job(
        self,
        job_id: uuid.UUID,
        schedule_type: str,
        run_fn: Any = None,
        cron_expression: str | None = None,
        **kwargs: Any,
    ) -> str:
        """Create and register a new ETL schedule.

        Args:
            job_id: ETL job UUID.
            schedule_type: Recurrence type (manual, hourly, daily, weekly, custom).
            run_fn: Optional callable to execute when schedule triggers.
            cron_expression: Optional cron syntax for custom schedules.
            **kwargs: Extra metadata parameters.

        Returns:
            str: Generated schedule_id.
        """
        try:
            freq = ScheduleFrequency(schedule_type.lower())
        except ValueError:
            freq = ScheduleFrequency.CUSTOM

        entry = ScheduledETLEntry(
            job_id=job_id,
            frequency=freq,
            cron_expression=cron_expression,
            metadata=kwargs,
        )
        entry.calculate_next_run()

        self._schedules[entry.schedule_id] = entry
        logger.info(
            "etl_job_scheduled",
            schedule_id=entry.schedule_id,
            job_id=str(job_id),
            frequency=freq.value,
            next_run=entry.next_run_at.isoformat() if entry.next_run_at else None,
        )
        return entry.schedule_id

    def cancel_schedule(self, schedule_id: str) -> bool:
        """Cancel and deactivate a scheduled sync job.

        Args:
            schedule_id: Identifier of schedule to cancel.

        Returns:
            bool: True if found and cancelled.
        """
        if schedule_id in self._schedules:
            self._schedules[schedule_id].is_active = False
            logger.info("etl_schedule_cancelled", schedule_id=schedule_id)
            return True
        return False

    def get_schedule(self, schedule_id: str) -> ScheduledETLEntry | None:
        """Retrieve schedule record by ID."""
        return self._schedules.get(schedule_id)

    def list_schedules(self, active_only: bool = True) -> list[ScheduledETLEntry]:
        """List all registered schedules."""
        if active_only:
            return [s for s in self._schedules.values() if s.is_active]
        return list(self._schedules.values())
