"""Domain Events and Event Dispatcher Package for Investiga.

Provides domain event definitions and in-memory event dispatching.
"""

from app.common.events.dispatcher import (
    EventDispatcherInterface,
    EventHandler,
    InMemoryEventDispatcher,
    get_event_dispatcher,
    set_event_dispatcher,
)
from app.common.events.events import (
    DocumentChunked,
    DocumentChunkedEvent,
    DocumentParsed,
    DocumentParsedEvent,
    DocumentUploaded,
    DocumentUploadedEvent,
    DomainEvent,
    EmbeddingsGenerated,
    EmbeddingsGeneratedEvent,
    IngestionCompleted,
    IngestionCompletedEvent,
    IngestionFailed,
    IngestionFailedEvent,
    VectorsIndexed,
    VectorsIndexedEvent,
)

__all__ = [
    "DocumentChunked",
    "DocumentChunkedEvent",
    "DocumentParsed",
    "DocumentParsedEvent",
    "DocumentUploaded",
    "DocumentUploadedEvent",
    "DomainEvent",
    "EmbeddingsGenerated",
    "EmbeddingsGeneratedEvent",
    "EventDispatcherInterface",
    "EventHandler",
    "InMemoryEventDispatcher",
    "IngestionCompleted",
    "IngestionCompletedEvent",
    "IngestionFailed",
    "IngestionFailedEvent",
    "VectorsIndexed",
    "VectorsIndexedEvent",
    "get_event_dispatcher",
    "set_event_dispatcher",
]
