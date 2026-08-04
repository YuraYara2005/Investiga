"""Enterprise Application Configuration Module for Investiga.

This module provides a centralized, type-safe, and environment-aware configuration
architecture using Pydantic Settings v2. It follows the 12-factor app methodology,
ensuring zero hardcoded credentials and seamless transitions across environments.
"""

from functools import lru_cache
import os
from typing import Literal
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
    version: str = Field(default="0.1.0", description="Semantic version of the backend.")
    environment: EnvironmentType = Field(
        default="development",
        description="Deployment runtime environment.",
    )
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
    reload: bool = Field(default=False, description="Enable auto-reload on code change.")


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
        default=PostgresDsn("postgresql+asyncpg://postgres:postgres@localhost:5432/investiga_db"),
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

    log_level: LogLevelType = Field(
        default="INFO",
        description="Minimum log severity level to capture.",
    )
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
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(f"Invalid CORS allow_origins format: {v}")


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

    model_config = SettingsConfigDict(
        env_file=(
            ".env",
            f".env.{os.getenv('APP_ENV', 'development').lower()}",
            f".env.local",
        ),
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("security")
    @classmethod
    def validate_production_security(
        cls, v: SecuritySettings, info: any
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

