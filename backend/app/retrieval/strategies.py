"""Retrieval Strategy Abstraction and Registry.

Defines the pluggable RetrievalStrategy base interface allowing arbitrary search
backends (Dense Vector, Sparse BM25, Graph, SQL, Web) to be orchestrated uniformly
by the HybridRetriever.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.retrieval.exceptions import StrategyNotFoundException
from app.retrieval.models import CandidateChunk, SearchFilters, SearchOptions


class RetrievalStrategy(ABC):
    """Abstract interface defining an independent retrieval strategy."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique strategy identifier (e.g. 'dense', 'bm25', 'graph')."""
        ...

    @abstractmethod
    async def retrieve(
        self,
        query: str,
        normalized_query: str,
        tokens: list[str],
        options: SearchOptions,
        filters: SearchFilters | None = None,
    ) -> list[CandidateChunk]:
        """Execute strategy retrieval returning candidate chunks.

        Args:
            query: Raw user query.
            normalized_query: Preprocessed normalized query string.
            tokens: Linguistic tokens extracted for lexical matching.
            options: Search options including candidate limits and collection name.
            filters: Structured metadata filters.

        Returns:
            list[CandidateChunk]: Ranked list of candidate chunks with scores and ranks.
        """
        ...


class StrategyRegistry:
    """Registry maintaining active retrieval strategies for the hybrid engine."""

    def __init__(self) -> None:
        self._strategies: dict[str, RetrievalStrategy] = {}

    def register(self, strategy: RetrievalStrategy) -> None:
        """Register a retrieval strategy implementation."""
        self._strategies[strategy.name.lower()] = strategy

    def get(self, name: str) -> RetrievalStrategy:
        """Get strategy by name.

        Raises:
            StrategyNotFoundException: If strategy is not registered.
        """
        norm_name = name.lower().strip()
        if norm_name not in self._strategies:
            raise StrategyNotFoundException(strategy_name=name)
        return self._strategies[norm_name]

    def list_strategies(self) -> list[str]:
        """Return list of all registered strategy names."""
        return list(self._strategies.keys())
