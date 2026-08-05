"""Vector Store Metadata Filter Builder.

Provides a fluent, provider-agnostic DSL for building structured metadata
filter queries (must, should, must_not, range, match, in) that translate cleanly
to vector database filter specifications.
"""

from __future__ import annotations

import uuid
from typing import Any

from app.vectorstore.exceptions import InvalidFilterException


class FilterCondition:
    """Internal condition representation for a single metadata field."""

    def __init__(
        self,
        key: str,
        op: str,
        value: Any = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        self.key = key
        self.op = op  # "exact", "in", "range", "match_text"
        self.value = value
        self.extra = extra or {}

    def to_dict(self) -> dict[str, Any]:
        """Serialize condition to dictionary."""
        res: dict[str, Any] = {"key": self.key, "op": self.op}
        if self.value is not None:
            if isinstance(self.value, uuid.UUID):
                res["value"] = str(self.value)
            elif isinstance(self.value, list):
                res["value"] = [
                    str(v) if isinstance(v, uuid.UUID) else v for v in self.value
                ]
            else:
                res["value"] = self.value
        if self.extra:
            res["extra"] = self.extra
        return res


class MetadataFilterBuilder:
    """Fluent query builder for constructing vector metadata filtering expressions."""

    def __init__(self) -> None:
        self._must: list[FilterCondition] = []
        self._should: list[FilterCondition] = []
        self._must_not: list[FilterCondition] = []

    def must(self, key: str, value: Any) -> MetadataFilterBuilder:
        """Add an exact match condition that MUST be satisfied (logical AND)."""
        if not key or not key.strip():
            raise InvalidFilterException("Filter key cannot be empty.")
        val = str(value) if isinstance(value, uuid.UUID) else value
        self._must.append(FilterCondition(key=key.strip(), op="exact", value=val))
        return self

    def should(self, key: str, value: Any) -> MetadataFilterBuilder:
        """Add a match condition that SHOULD be satisfied (logical OR)."""
        if not key or not key.strip():
            raise InvalidFilterException("Filter key cannot be empty.")
        val = str(value) if isinstance(value, uuid.UUID) else value
        self._should.append(FilterCondition(key=key.strip(), op="exact", value=val))
        return self

    def must_not(self, key: str, value: Any) -> MetadataFilterBuilder:
        """Add a condition that MUST NOT be satisfied (logical NOT)."""
        if not key or not key.strip():
            raise InvalidFilterException("Filter key cannot be empty.")
        val = str(value) if isinstance(value, uuid.UUID) else value
        self._must_not.append(FilterCondition(key=key.strip(), op="exact", value=val))
        return self

    def filter_in(self, key: str, values: list[Any]) -> MetadataFilterBuilder:
        """Add condition where key value must be contained in the provided list."""
        if not key or not key.strip():
            raise InvalidFilterException("Filter key cannot be empty.")
        if not values:
            raise InvalidFilterException("Values list cannot be empty for 'in' filter.")
        serialized_values = [str(v) if isinstance(v, uuid.UUID) else v for v in values]
        self._must.append(
            FilterCondition(key=key.strip(), op="in", value=serialized_values)
        )
        return self

    def filter_range(
        self,
        key: str,
        gte: float | int | None = None,
        lte: float | int | None = None,
        gt: float | int | None = None,
        lt: float | int | None = None,
    ) -> MetadataFilterBuilder:
        """Add a numerical range boundary condition."""
        if not key or not key.strip():
            raise InvalidFilterException("Filter key cannot be empty.")
        if gte is None and lte is None and gt is None and lt is None:
            raise InvalidFilterException(
                "At least one boundary (gte, lte, gt, lt) must be specified for range filter."
            )

        range_args: dict[str, Any] = {}
        if gte is not None:
            range_args["gte"] = gte
        if lte is not None:
            range_args["lte"] = lte
        if gt is not None:
            range_args["gt"] = gt
        if lt is not None:
            range_args["lt"] = lt

        self._must.append(
            FilterCondition(key=key.strip(), op="range", extra=range_args)
        )
        return self

    def filter_match(self, key: str, text: str) -> MetadataFilterBuilder:
        """Add a full-text or substring match condition on a text field."""
        if not key or not key.strip():
            raise InvalidFilterException("Filter key cannot be empty.")
        if not text or not text.strip():
            raise InvalidFilterException("Match text cannot be empty.")
        self._must.append(
            FilterCondition(key=key.strip(), op="match_text", value=text.strip())
        )
        return self

    def filter_tenant(self, tenant_id: str | uuid.UUID) -> MetadataFilterBuilder:
        """Convenience method to apply multi-tenant isolation boundary."""
        return self.must("tenant_id", str(tenant_id))

    def filter_workspace(self, workspace_id: str | uuid.UUID) -> MetadataFilterBuilder:
        """Convenience method to apply workspace isolation boundary."""
        return self.must("workspace_id", str(workspace_id))

    def filter_document(self, document_id: str | uuid.UUID) -> MetadataFilterBuilder:
        """Convenience method to filter vectors by parent document ID."""
        return self.must("document_id", str(document_id))

    def is_empty(self) -> bool:
        """Return True if no filter conditions have been defined."""
        return (
            len(self._must) == 0 and len(self._should) == 0 and len(self._must_not) == 0
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert filter builder state into an agnostic structured dictionary."""
        return {
            "must": [c.to_dict() for c in self._must],
            "should": [c.to_dict() for c in self._should],
            "must_not": [c.to_dict() for c in self._must_not],
        }

    def to_qdrant_filter(self) -> Any:
        """Translate filter conditions into a Qdrant `models.Filter` object.

        Returns:
            qdrant_client.models.Filter instance, or None if no conditions exist.
        """
        if self.is_empty():
            return None

        try:
            from qdrant_client import models
        except ImportError as e:
            raise InvalidFilterException(
                "qdrant-client package is required to build Qdrant filters."
            ) from e

        def _build_field_conditions(conditions: list[FilterCondition]) -> list[Any]:
            qdrant_conds: list[Any] = []
            for cond in conditions:
                if cond.op == "exact":
                    qdrant_conds.append(
                        models.FieldCondition(
                            key=cond.key,
                            match=models.MatchValue(value=cond.value),
                        )
                    )
                elif cond.op == "in":
                    qdrant_conds.append(
                        models.FieldCondition(
                            key=cond.key,
                            match=models.MatchAny(any=cond.value),
                        )
                    )
                elif cond.op == "range":
                    qdrant_conds.append(
                        models.FieldCondition(
                            key=cond.key,
                            range=models.Range(**cond.extra),
                        )
                    )
                elif cond.op == "match_text":
                    qdrant_conds.append(
                        models.FieldCondition(
                            key=cond.key,
                            match=models.MatchText(text=cond.value),
                        )
                    )
            return qdrant_conds

        must_conditions = _build_field_conditions(self._must) or None
        should_conditions = _build_field_conditions(self._should) or None
        must_not_conditions = _build_field_conditions(self._must_not) or None

        return models.Filter(
            must=must_conditions,
            should=should_conditions,
            must_not=must_not_conditions,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MetadataFilterBuilder:
        """Construct a builder from a dictionary representation."""
        builder = cls()
        for item in data.get("must", []):
            op = item.get("op", "exact")
            if op == "exact":
                builder.must(item["key"], item["value"])
            elif op == "in":
                builder.filter_in(item["key"], item["value"])
            elif op == "range":
                extra = item.get("extra", {})
                builder.filter_range(item["key"], **extra)
            elif op == "match_text":
                builder.filter_match(item["key"], item["value"])

        for item in data.get("should", []):
            builder.should(item["key"], item["value"])

        for item in data.get("must_not", []):
            builder.must_not(item["key"], item["value"])

        return builder
