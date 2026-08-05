"""Enterprise Application Configuration Module for Investiga.

This module provides a centralized, type-safe, and environment-aware configuration
architecture using Pydantic Settings v2. It follows the 12-factor app methodology,
ensuring zero hardcoded credentials and seamless transitions across environments.
"""

import os
from functools import lru_cache
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, PostgresDsn, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

EnvironmentType = Literal["development", "staging", "production", "test"]
LogLevelType = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class AppSettings(BaseModel):
    """General application metadata and operational parameters."""

    name: str = Field(default="Investiga", description="Application display name.")
    tagline: str = Field(
        default="AI-Powered Incident Investigation Platform",
        description="Application tagline.",
    )
    version: str = Field(
        default="0.1.0", description="Semantic version of the backend."
    )
    environment: Annotated[
        EnvironmentType,
        Field(description="Deployment runtime environment."),
    ] = "development"
    debug: bool = Field(
        default=False,
        description="Debug mode enabling verbose traces and auto-reloading.",
    )
    api_v1_prefix: str = Field(
        default="/api/v1",
        description="Route prefix for Version 1 API endpoints.",
    )

    @property
    def is_production(self) -> bool:
        """Helper to check if running in production mode."""
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        """Helper to check if running in development mode."""
        return self.environment == "development"

    @property
    def is_testing(self) -> bool:
        """Helper to check if running in automated test mode."""
        return self.environment == "test"


class ServerSettings(BaseModel):
    """Uvicorn and HTTP transport settings."""

    host: str = Field(default="0.0.0.0", description="Network host interface to bind.")
    port: int = Field(default=8000, description="Network TCP port to bind.")
    workers: int = Field(default=1, description="Number of ASGI worker processes.")
    reload: bool = Field(
        default=False, description="Enable auto-reload on code change."
    )


class SecuritySettings(BaseModel):
    """Cryptographic, authentication, and token management configuration."""

    secret_key: SecretStr = Field(
        default=SecretStr(
            "insecure-default-change-in-production-09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"
        ),
        description="Cryptographic secret key for signing JWTs and HMAC tokens.",
    )
    algorithm: str = Field(
        default="HS256",
        description="Cryptographic signing algorithm for JWT tokens.",
    )
    access_token_expire_minutes: int = Field(
        default=30,
        ge=1,
        description="Lifespan of short-lived access tokens in minutes.",
    )
    refresh_token_expire_days: int = Field(
        default=7,
        ge=1,
        description="Lifespan of long-lived refresh tokens in days.",
    )


class DatabaseSettings(BaseModel):
    """Asynchronous PostgreSQL connection and connection pooling parameters."""

    url: PostgresDsn = Field(
        default=PostgresDsn(
            "postgresql+asyncpg://postgres:postgres@localhost:5432/investiga_db"
        ),
        description="Asynchronous database connection string with asyncpg driver.",
    )
    pool_size: int = Field(
        default=10,
        ge=1,
        description="Base number of persistent database connections maintained in the pool.",
    )
    max_overflow: int = Field(
        default=20,
        ge=0,
        description="Maximum temporary connections allowed beyond pool_size during traffic spikes.",
    )
    pool_timeout: int = Field(
        default=30,
        ge=1,
        description="Seconds to wait before throwing a connection timeout error.",
    )
    pool_recycle: int = Field(
        default=1800,
        ge=1,
        description="Recycle connections older than this number of seconds to avoid stale TCP sockets.",
    )
    echo_sql: bool = Field(
        default=False,
        description="Log all emitted SQL statements (recommended false in production).",
    )

    @field_validator("url")
    @classmethod
    def validate_asyncpg_driver(cls, v: PostgresDsn) -> PostgresDsn:
        """Enforce asyncpg driver for strictly asynchronous operation."""
        scheme = v.scheme
        if scheme != "postgresql+asyncpg":
            raise ValueError(
                f"Database URL scheme must be 'postgresql+asyncpg', received '{scheme}'. "
                "Synchronous database drivers are strictly forbidden in Investiga."
            )
        return v


class LoggingSettings(BaseModel):
    """Structured logging configuration."""

    log_level: Annotated[
        LogLevelType,
        Field(description="Minimum log severity level to capture."),
    ] = "INFO"
    json_logs: bool = Field(
        default=False,
        description="Render logs as JSON strings (True for production/Kubernetes, False for local console).",
    )


class CORSSettings(BaseModel):
    """Cross-Origin Resource Sharing (CORS) access control policies."""

    allow_origins: list[str] = Field(
        default=["http://localhost:3000", "http://127.0.0.1:3000"],
        description="Allowed CORS origin domains.",
    )
    allow_credentials: bool = Field(
        default=True,
        description="Permit browser cookies and credentials in CORS requests.",
    )
    allow_methods: list[str] = Field(
        default=["*"],
        description="Allowed HTTP methods.",
    )
    allow_headers: list[str] = Field(
        default=["*"],
        description="Allowed HTTP request headers.",
    )

    @field_validator("allow_origins", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: str | list[str]) -> list[str]:
        """Parse comma-separated strings or JSON arrays into a list of origins."""
        if isinstance(v, str):
            if not v.startswith("["):
                return [i.strip() for i in v.split(",") if i.strip()]
            import json

            parsed = json.loads(v)
            if isinstance(parsed, list):
                return [str(item) for item in parsed]
            return [str(parsed)]
        elif isinstance(v, list):
            return [str(item) for item in v]
        raise ValueError(f"Invalid CORS allow_origins format: {v}")


class StorageSettings(BaseModel):
    """File storage and upload infrastructure configuration."""

    upload_directory: str = Field(
        default="data/uploads",
        description="Base directory path on filesystem to store uploaded files.",
    )
    max_upload_size_mb: int = Field(
        default=50,
        ge=1,
        description="Maximum permitted single file upload size in megabytes.",
    )
    allowed_extensions: list[str] = Field(
        default=[
            ".pdf",
            ".docx",
            ".txt",
            ".md",
            ".json",
            ".yaml",
            ".yml",
            ".csv",
            ".log",
        ],
        description="Allowed file extensions for ingestion.",
    )
    allowed_mime_types: list[str] = Field(
        default=[
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "text/plain",
            "text/markdown",
            "application/json",
            "application/x-yaml",
            "text/yaml",
            "text/csv",
        ],
        description="Allowed IANA MIME types for uploaded files.",
    )


class ChunkingSettings(BaseModel):
    """Intelligent document chunking pipeline configuration."""

    chunk_size: int = Field(
        default=512,
        ge=64,
        le=8192,
        description="Maximum number of tokens per chunk.",
    )
    overlap: int = Field(
        default=64,
        ge=0,
        description="Number of overlapping tokens between consecutive chunks.",
    )
    strategy: str = Field(
        default="adaptive",
        description="Default chunking strategy: fixed_character | recursive_character | sentence | paragraph | markdown_header | adaptive.",
    )
    tokenizer_encoding: str = Field(
        default="cl100k_base",
        description="tiktoken encoding to use for token counting (cl100k_base for GPT-4).",
    )
    avg_chars_per_page: int = Field(
        default=3000,
        ge=500,
        description="Average character count per page, used to estimate page numbers from offsets.",
    )


class EmbeddingSettings(BaseModel):
    """Embedding model and inference pipeline configuration."""

    model_name: str = Field(
        default="BAAI/bge-base-en-v1.5",
        description="Default embedding model identifier from HuggingFace Hub or local path.",
    )
    dimension: int = Field(
        default=768,
        ge=1,
        description="Expected embedding vector dimension.",
    )
    batch_size: int = Field(
        default=32,
        ge=1,
        le=512,
        description="Default batch size for model inference.",
    )
    max_seq_length: int = Field(
        default=512,
        ge=1,
        description="Maximum token sequence length allowed by the model.",
    )
    normalize_embeddings: bool = Field(
        default=True,
        description="Whether to L2-normalize output embeddings.",
    )
    device: str = Field(
        default="",
        description="Compute device override ('cuda', 'mps', 'cpu', or empty for auto-detect).",
    )
    cache_folder: str = Field(
        default="",
        description="Local directory path to cache downloaded embedding model weights.",
    )
    adaptive_batching: bool = Field(
        default=True,
        description="Whether to adaptively adjust batch size based on input token lengths.",
    )


class VectorStoreSettings(BaseModel):
    """Vector database storage and retrieval configuration."""

    provider: str = Field(
        default="qdrant",
        description="Vector store provider backend ('qdrant', 'milvus', 'pinecone', 'weaviate', 'faiss').",
    )
    host: str = Field(
        default="localhost",
        description="Vector database server hostname or IP.",
    )
    port: int = Field(
        default=6333,
        ge=1,
        le=65535,
        description="HTTP/REST port for vector database connection.",
    )
    grpc_port: int = Field(
        default=6334,
        ge=1,
        le=65535,
        description="gRPC port for high-performance vector database communication.",
    )
    prefer_grpc: bool = Field(
        default=True,
        description="Whether to prioritize gRPC connection over HTTP/REST.",
    )
    https: bool = Field(
        default=False,
        description="Whether to use TLS/HTTPS encryption for connections.",
    )
    api_key: SecretStr | None = Field(
        default=None,
        description="Optional API key for authenticated or managed vector database instances.",
    )
    collection_name: str = Field(
        default="investiga_knowledge",
        description="Default vector collection / index name for knowledge chunks.",
    )
    distance_metric: str = Field(
        default="cosine",
        description="Distance metric for similarity calculations ('cosine', 'dot', 'euclidean', 'manhattan').",
    )
    vector_size: int = Field(
        default=768,
        ge=1,
        description="Dimensionality of stored vector embeddings (defaults to match default embedding model).",
    )
    replication_factor: int = Field(
        default=1,
        ge=1,
        description="Number of replicas for distributed clustering.",
    )
    write_consistency: str = Field(
        default="majority",
        description="Write consistency requirement ('majority', 'all', 'quorum', 'one').",
    )
    batch_size: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Maximum number of vector records per batch upsert operation.",
    )
    timeout: float = Field(
        default=10.0,
        ge=0.1,
        description="Request timeout in seconds for vector database operations.",
    )
    max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Maximum retry attempts with exponential backoff on transient network failures.",
    )


class RetrievalSettings(BaseModel):
    """Configuration settings for Enterprise Hybrid Retrieval Engine."""

    enabled_dense: bool = Field(
        default=True,
        description="Whether dense vector similarity search strategy is enabled.",
    )
    enabled_sparse: bool = Field(
        default=True,
        description="Whether sparse BM25 keyword search strategy is enabled.",
    )
    dense_weight: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Relative weight coefficient assigned to dense retrieval.",
    )
    sparse_weight: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Relative weight coefficient assigned to sparse BM25 retrieval.",
    )
    fusion_strategy: str = Field(
        default="rrf",
        description="Fusion strategy name ('rrf', 'weighted_linear', 'combsum').",
    )
    rrf_k: int = Field(
        default=60,
        ge=1,
        le=1000,
        description="Reciprocal Rank Fusion smoothing constant k.",
    )
    top_k: int = Field(
        default=20,
        ge=1,
        le=1000,
        description="Default number of ranked chunks to return to caller.",
    )
    dense_candidate_limit: int = Field(
        default=50,
        ge=1,
        le=1000,
        description="Number of candidate records to retrieve from dense vector index before fusion.",
    )
    sparse_candidate_limit: int = Field(
        default=50,
        ge=1,
        le=1000,
        description="Number of candidate records to retrieve from BM25 sparse index before fusion.",
    )
    min_score_threshold: float = Field(
        default=0.0,
        ge=0.0,
        description="Minimum score threshold for a chunk to be included in final results.",
    )
    bm25_k1: float = Field(
        default=1.5,
        ge=0.0,
        le=5.0,
        description="BM25 term frequency saturation parameter k1.",
    )
    bm25_b: float = Field(
        default=0.75,
        ge=0.0,
        le=1.0,
        description="BM25 document length normalization parameter b.",
    )
    bm25_epsilon: float = Field(
        default=0.25,
        ge=0.0,
        description="BM25 negative IDF lower bound floor threshold.",
    )
    enable_cache: bool = Field(
        default=True,
        description="Whether query and retrieval result caching is enabled.",
    )
    cache_ttl_seconds: int = Field(
        default=300,
        ge=1,
        description="Time-to-live in seconds for cached retrieval entries.",
    )
    cache_max_size: int = Field(
        default=1000,
        ge=10,
        description="Maximum entries stored in the in-memory retrieval cache.",
    )
    timeout_seconds: float = Field(
        default=10.0,
        ge=0.1,
        description="Global timeout in seconds for retrieval execution.",
    )
    max_query_length: int = Field(
        default=4096,
        ge=1,
        description="Maximum permitted character length for search queries.",
    )


class RAGSettings(BaseModel):
    """Configuration parameters for the Enterprise RAG Generation Engine."""

    llm_provider: str = Field(
        default="gemini",
        description="Default LLM provider backend ('gemini', 'ollama', 'mock').",
    )
    gemini_api_key: SecretStr = Field(
        default=SecretStr(""),
        description="Google Gemini API key.",
    )
    gemini_model: str = Field(
        default="gemini-1.5-flash",
        description="Default Google Gemini model name.",
    )
    gemini_api_base_url: str = Field(
        default="https://generativelanguage.googleapis.com/v1beta",
        description="Base URL for Google Gemini API endpoints.",
    )
    ollama_base_url: str = Field(
        default="http://localhost:11434",
        description="Base URL for local Ollama API server.",
    )
    ollama_model: str = Field(
        default="llama3",
        description="Default Ollama model name.",
    )
    max_output_tokens: int = Field(
        default=2048,
        ge=1,
        le=32768,
        description="Maximum token generation limit for LLM responses.",
    )
    temperature: float = Field(
        default=0.2,
        ge=0.0,
        le=2.0,
        description="Sampling temperature for generation randomness.",
    )
    top_p: float = Field(
        default=0.95,
        ge=0.0,
        le=1.0,
        description="Nucleus sampling probability cutoff.",
    )
    context_token_budget: int = Field(
        default=4000,
        ge=100,
        le=128000,
        description="Total token budget allocated for retrieved context in prompt.",
    )
    min_relevance_threshold: float = Field(
        default=0.01,
        ge=0.0,
        description="Minimum relevance confidence threshold to trigger generation.",
    )
    prompt_strategy: str = Field(
        default="standard_qa",
        description="Default prompt strategy name ('standard_qa', 'investigative_analysis', 'executive_summary', 'extractive', 'concise').",
    )
    enable_guardrails: bool = Field(
        default=True,
        description="Whether pre-generation and post-generation guardrails are enforced.",
    )
    fallback_message: str = Field(
        default="I do not have sufficient information in the provided knowledge base to answer this question accurately.",
        description="Safe response returned when context is inadequate or guardrails reject generation.",
    )
    retry_max_attempts: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum retry attempts on transient LLM provider failures.",
    )
    retry_backoff_factor: float = Field(
        default=1.5,
        ge=1.0,
        le=5.0,
        description="Exponential backoff multiplier for retries.",
    )
    timeout_seconds: float = Field(
        default=30.0,
        ge=1.0,
        le=300.0,
        description="Timeout in seconds for upstream LLM generation calls.",
    )


class Settings(BaseSettings):
    """Root configuration object composing all architectural subsystems.

    Loads values from environment variables and cascading `.env` files with
    double-underscore nested key delimiters (e.g., `APP__NAME=Investiga`,
    `DATABASE__URL=postgresql+asyncpg://...`).
    """

    app: AppSettings = Field(default_factory=AppSettings)
    server: ServerSettings = Field(default_factory=ServerSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    cors: CORSSettings = Field(default_factory=CORSSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    chunking: ChunkingSettings = Field(default_factory=ChunkingSettings)
    embeddings: EmbeddingSettings = Field(default_factory=EmbeddingSettings)
    vectorstore: VectorStoreSettings = Field(default_factory=VectorStoreSettings)
    retrieval: RetrievalSettings = Field(default_factory=RetrievalSettings)
    rag: RAGSettings = Field(default_factory=RAGSettings)

    model_config = SettingsConfigDict(
        env_file=(
            ".env",
            f".env.{os.getenv('APP_ENV', 'development').lower()}",
            ".env.local",
        ),
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("security")
    @classmethod
    def validate_production_security(
        cls, v: SecuritySettings, info: Any
    ) -> SecuritySettings:
        """Prevent launching in production with default/insecure secret keys."""
        return v

    def validate_environment_integrity(self) -> None:
        """Perform cross-domain validation checks across nested setting models."""
        if self.app.is_production:
            raw_secret = self.security.secret_key.get_secret_value()
            if "insecure-default" in raw_secret or len(raw_secret) < 32:
                raise ValueError(
                    "CRITICAL SECURITY VIOLATION: Application cannot start in production "
                    "with a default or weak secret key. Set SECURITY__SECRET_KEY to a secure value."
                )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Retrieve the cached singleton application settings instance.

    Uses `functools.lru_cache` to eliminate disk I/O and repetitive parsing overhead
    during FastAPI dependency injection while preserving testability via cache clearing.

    Returns:
        Settings: The validated application configuration instance.
    """
    settings = Settings()
    settings.validate_environment_integrity()
    return settings
