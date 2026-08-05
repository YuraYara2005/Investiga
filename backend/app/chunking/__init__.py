"""Intelligent Chunking Subsystem for Investiga.

Provides enterprise-grade document chunking with multiple semantic strategies,
deterministic chunk IDs, token-accurate overlap, and metadata preservation.
"""

from app.chunking.chunker import ChunkingEngine
from app.chunking.exceptions import (
    ChunkingException,
    EmptyTextException,
    InvalidChunkConfigException,
)
from app.chunking.models import Chunk, ChunkMetadata, ChunkResult
from app.chunking.strategies import (
    AdaptiveChunker,
    BaseChunkStrategy,
    FixedCharacterChunker,
    MarkdownHeaderChunker,
    ParagraphChunker,
    RecursiveCharacterChunker,
    SentenceChunker,
)
from app.chunking.tokenizer import Tokenizer, get_tokenizer

__all__ = [
    "AdaptiveChunker",
    "BaseChunkStrategy",
    "Chunk",
    "ChunkMetadata",
    "ChunkResult",
    "ChunkingEngine",
    "ChunkingException",
    "EmptyTextException",
    "FixedCharacterChunker",
    "InvalidChunkConfigException",
    "MarkdownHeaderChunker",
    "ParagraphChunker",
    "RecursiveCharacterChunker",
    "SentenceChunker",
    "Tokenizer",
    "get_tokenizer",
]
