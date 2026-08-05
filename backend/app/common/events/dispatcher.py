"""In-Process Domain Event Dispatcher for Investiga.

Provides asynchronous, decoupled event dispatching within the current application
process. Handlers can subscribe to specific domain event types and execute asynchronously
without blocking the main operational flow.
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import Callable, Coroutine
from typing import Any, TypeVar

from app.common.events.events import DomainEvent
from app.core.logging import get_logger

logger = get_logger(__name__)

E = TypeVar("E", bound=DomainEvent)
EventHandler = Callable[[E], Coroutine[Any, Any, None]]


class EventDispatcherInterface(ABC):
    """Abstract contract for publishing and subscribing to domain events."""

    @abstractmethod
    def subscribe(
        self,
        event_type: type[E],
        handler: EventHandler[E],
    ) -> None:
        """Register an asynchronous subscriber for a specific event class."""
        pass

    @abstractmethod
    def unsubscribe(
        self,
        event_type: type[E],
        handler: EventHandler[E],
    ) -> None:
        """Remove an existing subscriber for a specific event class."""
        pass

    @abstractmethod
    async def publish(self, event: DomainEvent) -> None:
        """Asynchronously dispatch an event to all registered subscribers."""
        pass


class InMemoryEventDispatcher(EventDispatcherInterface):
    """Lightweight in-memory event dispatcher executing handlers asynchronously."""

    def __init__(self) -> None:
        self._subscribers: dict[type[DomainEvent], list[EventHandler[Any]]] = (
            defaultdict(list)
        )
        self._lock = asyncio.Lock()

    def subscribe(
        self,
        event_type: type[E],
        handler: EventHandler[E],
    ) -> None:
        """Register an asynchronous handler for the specified domain event type."""
        handlers = self._subscribers[event_type]
        if handler not in handlers:
            handlers.append(handler)
            logger.debug(
                "event_handler_subscribed",
                event_type=event_type.__name__,
                handler=getattr(handler, "__name__", str(handler)),
            )

    def unsubscribe(
        self,
        event_type: type[E],
        handler: EventHandler[E],
    ) -> None:
        """Unsubscribe a registered handler."""
        if event_type in self._subscribers:
            handlers = self._subscribers[event_type]
            if handler in handlers:
                handlers.remove(handler)
                logger.debug(
                    "event_handler_unsubscribed",
                    event_type=event_type.__name__,
                    handler=getattr(handler, "__name__", str(handler)),
                )

    async def publish(self, event: DomainEvent) -> None:
        """Dispatch a domain event to all registered subscribers.

        Executes handlers safely so that an error in one handler does not prevent
        other handlers or the main ingestion pipeline from executing.
        """
        event_cls = type(event)
        handlers: list[EventHandler[Any]] = []

        # Find direct and polymorphic subscribers
        for registered_cls, registered_handlers in self._subscribers.items():
            if issubclass(event_cls, registered_cls):
                handlers.extend(registered_handlers)

        if not handlers:
            logger.debug("no_event_subscribers", event_type=event.event_type)
            return

        logger.debug(
            "dispatching_event",
            event_type=event.event_type,
            subscriber_count=len(handlers),
            event_id=str(event.event_id),
        )

        # Execute handlers concurrently
        tasks = [self._execute_safe(handler, event) for handler in handlers]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _execute_safe(
        self, handler: EventHandler[Any], event: DomainEvent
    ) -> None:
        """Execute a single handler with structured error containment."""
        handler_name = getattr(handler, "__name__", str(handler))
        try:
            await handler(event)
        except Exception as exc:
            logger.error(
                "event_handler_execution_failed",
                event_type=event.event_type,
                event_id=str(event.event_id),
                handler=handler_name,
                error=str(exc),
                exc_info=True,
            )

    def clear(self) -> None:
        """Clear all registered event subscriptions (primarily for test teardown)."""
        self._subscribers.clear()


# Global singleton holder
_GLOBAL_DISPATCHER: InMemoryEventDispatcher | None = None


def get_event_dispatcher() -> InMemoryEventDispatcher:
    """Retrieve or lazily initialize the singleton in-memory event dispatcher."""
    global _GLOBAL_DISPATCHER
    if _GLOBAL_DISPATCHER is None:
        _GLOBAL_DISPATCHER = InMemoryEventDispatcher()
    return _GLOBAL_DISPATCHER


def set_event_dispatcher(dispatcher: InMemoryEventDispatcher | None) -> None:
    """Explicitly set or reset the global event dispatcher."""
    global _GLOBAL_DISPATCHER
    _GLOBAL_DISPATCHER = dispatcher
