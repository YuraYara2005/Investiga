"""Response DTO Schemas for Identity and Authentication in Investiga.

This module defines outbound data models ensuring internal database models
(and sensitive fields like `hashed_password`) are never leaked to API consumers.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class PermissionResponse(BaseModel):
    """Response schema representing an individual authorization entitlement."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    resource: str
    action: str
    description: str | None = None


class RoleResponse(BaseModel):
    """Response schema representing a functional user role."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    display_name: str
    description: str | None = None
    is_system_role: bool


class UserResponse(BaseModel):
    """Response schema representing a sanitized user identity record."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    full_name: str
    is_active: bool
    is_verified: bool
    is_superuser: bool
    roles: list[str] = Field(default_factory=list)
    created_at: datetime
    last_login_at: datetime | None = None


class CurrentUserResponse(BaseModel):
    """Detailed response schema for the authenticated principal including all active claims."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    full_name: str
    is_active: bool
    is_verified: bool
    is_superuser: bool
    roles: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)
    created_at: datetime
    last_login_at: datetime | None = None


class TokenResponse(BaseModel):
    """Response schema returned upon successful authentication containing JWT tokens."""

    model_config = ConfigDict(from_attributes=True)

    access_token: str = Field(
        ...,
        description="Stateless short-lived JWT access token for API authorization.",
    )
    refresh_token: str = Field(
        ...,
        description="Long-lived cryptographic refresh token for session extension.",
    )
    token_type: str = Field(
        default="Bearer",
        description="OAuth2 authorization token type.",
    )
    expires_in: int = Field(
        ...,
        description="Access token lifespan duration in seconds.",
    )
