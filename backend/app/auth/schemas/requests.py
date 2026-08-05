"""Request DTO Schemas for Identity and Authentication in Investiga.

This module defines Pydantic v2 validation models for incoming client payloads,
enforcing structure, typing, and input constraints before reaching the service layer.
"""

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserRegisterRequest(BaseModel):
    """Payload schema for registering a new user account."""

    model_config = ConfigDict(str_strip_whitespace=True)

    email: EmailStr = Field(
        ...,
        description="Canonical user corporate email address.",
        examples=["analyst.jane@investiga.internal"],
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Plaintext password complying with corporate password complexity policies.",
        examples=["Investiga#2026!Secure"],
    )
    full_name: str = Field(
        ...,
        min_length=2,
        max_length=255,
        description="Full professional name of the user.",
        examples=["Jane Doe"],
    )


class UserLoginRequest(BaseModel):
    """Payload schema for user credential authentication."""

    model_config = ConfigDict(str_strip_whitespace=True)

    email: EmailStr = Field(
        ...,
        description="Registered user email address.",
        examples=["analyst.jane@investiga.internal"],
    )
    password: str = Field(
        ...,
        description="Plaintext password string.",
        examples=["Investiga#2026!Secure"],
    )


class RefreshTokenRequest(BaseModel):
    """Payload schema for session renewal via refresh token."""

    model_config = ConfigDict(str_strip_whitespace=True)

    refresh_token: str = Field(
        ...,
        description="Valid long-lived JWT refresh token string.",
    )


class UpdateProfileRequest(BaseModel):
    """Payload schema for updating user profile information."""

    model_config = ConfigDict(str_strip_whitespace=True)

    full_name: str | None = Field(
        default=None,
        min_length=2,
        max_length=255,
        description="Updated professional full name.",
        examples=["Jane Smith"],
    )


class ChangePasswordRequest(BaseModel):
    """Payload schema for authenticated password modification."""

    model_config = ConfigDict(str_strip_whitespace=True)

    current_password: str = Field(
        ...,
        description="Current user password for identity re-verification.",
    )
    new_password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="New password complying with corporate complexity policies.",
    )
