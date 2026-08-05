"""Pluggable Rank Fusion Engine for Hybrid Retrieval.

Provides the FusionStrategy abstraction and concrete implementations including
Reciprocal Rank Fusion (RRF), Weighted Linear Fusion, and CombSUM, along with
score normalization utilities and deduplication routines.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from typing import Any

from app.retrieval.exceptions import FusionException, FusionStrategyNotFoundException
from app.retrieval.models import CandidateChunk, RetrievedChunk, SearchOptions


class ScoreNormalizer:
    """Statistical score normalization algorithms for heterogeneous retrieval rankings."""

    @staticmethod
    def min_max_normalize(scores: list[float]) -> list[float]:
        """Scale scores to the [0.0, 1.0] interval using Min-Max scaling.

        Args:
            scores: List of raw numerical scores.

        Returns:
            list[float]: Normalized scores in [0.0, 1.0].
        """
        if not scores:
            return []
        min_val = min(scores)
        max_val = max(scores)
        diff = max_val - min_val
        if diff == 0.0 or math.isclose(diff, 0.0):
            return [1.0] * len(scores)
        return [(s - min_val) / diff for s in scores]

    @staticmethod
    def z_score_normalize(scores: list[float]) -> list[float]:
        """Standardize scores using Z-Score (zero mean, unit variance), bounded with sigmoid.

        Args:
            scores: List of raw numerical scores.

        Returns:
            list[float]: Normalized scores transformed via logistic sigmoid.
        """
        if not scores:
            return []
        n = len(scores)
        if n == 1:
            return [1.0]
        mean = sum(scores) / n
        variance = sum((s - mean) ** 2 for s in scores) / n
        std_dev = math.sqrt(variance)
        if std_dev == 0.0 or math.isclose(std_dev, 0.0):
            return [1.0] * n

        normalized: list[float] = []
        for s in scores:
            z = (s - mean) / std_dev
            # Logistic sigmoid to bound into (0, 1)
            sig = 1.0 / (1.0 + math.exp(-z))
            normalized.append(sig)
        return normalized


class FusionStrategy(ABC):
    """Abstract interface defining hybrid rank fusion operations."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier name of the fusion strategy."""
        ...

    @abstractmethod
    def fuse(
        self,
        strategy_candidates: dict[str, list[CandidateChunk]],
        options: SearchOptions,
    ) -> list[RetrievedChunk]:
        """Combine candidate chunks from multiple retrieval strategies into a ranked list.

        Args:
            strategy_candidates: Mapping of strategy_name to candidate chunk lists.
            options: Runtime search options (weights, thresholds, top_k, rrf_k).

        Returns:
            list[RetrievedChunk]: Ranked, fused, deduplicated list of chunks.

        Raises:
            FusionException: If rank fusion calculation encounters an error.
        """
        ...


class ReciprocalRankFusion(FusionStrategy):
    """Standard Reciprocal Rank Fusion (RRF) algorithm.

    Computes:
        RRF_Score(d) = sum_{s in Strategies} ( weight_s * ( 1.0 / ( k + rank_s(d) ) ) )

    RRF is robust against score distribution discrepancies between dense embeddings
    and sparse lexical models because it relies strictly on ordinal ranking positions.
    """

    @property
    def name(self) -> str:
        return "rrf"

    def fuse(
        self,
        strategy_candidates: dict[str, list[CandidateChunk]],
        options: SearchOptions,
    ) -> list[RetrievedChunk]:
        try:
            k = options.rrf_k
            strategy_weights = {
                "dense": options.dense_weight,
                "bm25": options.sparse_weight,
            }

            # Map chunk_id -> aggregated fusion record
            fused_records: dict[str, dict[str, Any]] = {}

            for strat_name, candidates in strategy_candidates.items():
                strat_weight = strategy_weights.get(strat_name, 1.0)
                for cand in candidates:
                    cid = cand.chunk_id_str
                    if cid not in fused_records:
                        fused_records[cid] = {
                            "candidate": cand,
                            "rrf_score": 0.0,
                            "dense_score": None,
                            "dense_rank": None,
                            "sparse_score": None,
                            "sparse_rank": None,
                            "sources": set(),
                        }

                    entry = fused_records[cid]
                    rrf_increment = strat_weight * (1.0 / (k + cand.rank))
                    entry["rrf_score"] += rrf_increment
                    entry["sources"].add(strat_name)

                    if strat_name == "dense":
                        entry["dense_score"] = cand.score
                        entry["dense_rank"] = cand.rank
                    elif strat_name == "bm25":
                        entry["sparse_score"] = cand.score
                        entry["sparse_rank"] = cand.rank

            # Convert to RetrievedChunk instances
            result_chunks: list[RetrievedChunk] = []
            for _cid, data in fused_records.items():
                cand_chunk: CandidateChunk = data["candidate"]
                score = round(data["rrf_score"], 6)

                if score < options.min_score_threshold:
                    continue

                chunk = RetrievedChunk(
                    chunk_id=cand_chunk.chunk_id,
                    document_id=cand_chunk.document_id,
                    chunk_index=cand_chunk.chunk_index,
                    text=cand_chunk.text,
                    score=score,
                    dense_score=data["dense_score"],
                    dense_rank=data["dense_rank"],
                    sparse_score=data["sparse_score"],
                    sparse_rank=data["sparse_rank"],
                    retrieval_sources=sorted(data["sources"]),
                    heading=cand_chunk.heading,
                    page_number=cand_chunk.page_number,
                    title=cand_chunk.title,
                    file_name=cand_chunk.file_name,
                    category=cand_chunk.category,
                    tags=cand_chunk.tags,
                    metadata=cand_chunk.metadata,
                )
                result_chunks.append(chunk)

            # Sort descending by fused score
            result_chunks.sort(key=lambda c: c.score, reverse=True)

            return result_chunks[: options.top_k]

        except Exception as exc:
            raise FusionException(
                strategy_name=self.name,
                reason=f"Failed to execute Reciprocal Rank Fusion: {exc}",
            ) from exc


class WeightedLinearFusion(FusionStrategy):
    """Linear score combination with Min-Max score normalization.

    Computes:
        Score(d) = sum_{s in Strategies} ( weight_s * NormalizedScore_s(d) )
    """

    @property
    def name(self) -> str:
        return "weighted_linear"

    def fuse(
        self,
        strategy_candidates: dict[str, list[CandidateChunk]],
        options: SearchOptions,
    ) -> list[RetrievedChunk]:
        try:
            strategy_weights = {
                "dense": options.dense_weight,
                "bm25": options.sparse_weight,
            }

            # Normalize scores per strategy
            normalized_strategy_cands: dict[
                str, list[tuple[CandidateChunk, float]]
            ] = {}
            for strat_name, candidates in strategy_candidates.items():
                raw_scores = [c.score for c in candidates]
                norm_scores = ScoreNormalizer.min_max_normalize(raw_scores)
                normalized_strategy_cands[strat_name] = list(
                    zip(candidates, norm_scores, strict=False)
                )

            fused_records: dict[str, dict[str, Any]] = {}
            for strat_name, pairs in normalized_strategy_cands.items():
                strat_weight = strategy_weights.get(strat_name, 1.0)
                for cand, norm_score in pairs:
                    cid = cand.chunk_id_str
                    if cid not in fused_records:
                        fused_records[cid] = {
                            "candidate": cand,
                            "linear_score": 0.0,
                            "dense_score": None,
                            "dense_rank": None,
                            "sparse_score": None,
                            "sparse_rank": None,
                            "sources": set(),
                        }

                    entry = fused_records[cid]
                    entry["linear_score"] += strat_weight * norm_score
                    entry["sources"].add(strat_name)

                    if strat_name == "dense":
                        entry["dense_score"] = cand.score
                        entry["dense_rank"] = cand.rank
                    elif strat_name == "bm25":
                        entry["sparse_score"] = cand.score
                        entry["sparse_rank"] = cand.rank

            result_chunks: list[RetrievedChunk] = []
            for _cid, data in fused_records.items():
                cand = data["candidate"]
                score = round(data["linear_score"], 6)

                if score < options.min_score_threshold:
                    continue

                chunk = RetrievedChunk(
                    chunk_id=cand.chunk_id,
                    document_id=cand.document_id,
                    chunk_index=cand.chunk_index,
                    text=cand.text,
                    score=score,
                    dense_score=data["dense_score"],
                    dense_rank=data["dense_rank"],
                    sparse_score=data["sparse_score"],
                    sparse_rank=data["sparse_rank"],
                    retrieval_sources=sorted(data["sources"]),
                    heading=cand.heading,
                    page_number=cand.page_number,
                    title=cand.title,
                    file_name=cand.file_name,
                    category=cand.category,
                    tags=cand.tags,
                    metadata=cand.metadata,
                )
                result_chunks.append(chunk)

            result_chunks.sort(key=lambda c: c.score, reverse=True)
            return result_chunks[: options.top_k]

        except Exception as exc:
            raise FusionException(
                strategy_name=self.name,
                reason=f"Failed to execute Weighted Linear Fusion: {exc}",
            ) from exc


class CombSUMFusion(FusionStrategy):
    """CombSUM score combination (sum of normalized scores across retrieval runs)."""

    @property
    def name(self) -> str:
        return "combsum"

    def fuse(
        self,
        strategy_candidates: dict[str, list[CandidateChunk]],
        options: SearchOptions,
    ) -> list[RetrievedChunk]:
        # CombSUM is equivalent to WeightedLinearFusion with uniform weights
        equal_weight_options = options.model_copy(
            update={"dense_weight": 1.0, "sparse_weight": 1.0}
        )
        linear = WeightedLinearFusion()
        return linear.fuse(strategy_candidates, equal_weight_options)


class FusionEngine:
    """Registry and dispatcher for pluggable rank fusion strategies."""

    def __init__(self) -> None:
        self._strategies: dict[str, FusionStrategy] = {}
        # Register built-in strategies
        self.register(ReciprocalRankFusion())
        self.register(WeightedLinearFusion())
        self.register(CombSUMFusion())

    def register(self, strategy: FusionStrategy) -> None:
        """Register a new fusion strategy."""
        self._strategies[strategy.name.lower()] = strategy

    def get(self, name: str) -> FusionStrategy:
        """Lookup a fusion strategy by name.

        Raises:
            FusionStrategyNotFoundException: If strategy is not registered.
        """
        normalized_name = name.lower().strip()
        if normalized_name not in self._strategies:
            raise FusionStrategyNotFoundException(fusion_name=name)
        return self._strategies[normalized_name]
