"""Security and JWT Token Data Models for Investiga.

This module defines Pydantic v2 schemas for JWT token claims, validation models,
and response contracts for token issuance.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field

TokenType = Literal["access", "refresh"]


class TokenPayload(BaseModel):
    """Decoded and validated JWT claims payload.

    Conforms to RFC 7519 standard claims with domain-specific extensions for
    role-based access control (RBAC) and fine-grained permissions.

    Attributes:
        sub: Subject identifier (typically User UUID string).
        jti: Unique JWT ID (UUID string) for token revocation and replay defense.
        token_type: Discriminator ('access' vs 'refresh') to prevent token confusion attacks.
        exp: Expiration Unix epoch timestamp.
        iat: Issued-at Unix epoch timestamp.
        nbf: Not-before Unix epoch timestamp.
        iss: Token issuer identifier.
        roles: List of assigned role names (e.g. ['admin', 'investigator']).
        permissions: List of fine-grained permission codes.
        custom_claims: Optional dictionary containing arbitrary tenant/domain claims.
    """

    sub: str = Field(..., description="Subject unique identifier (User UUID).")
    jti: str = Field(..., description="Unique JWT ID for replay prevention and revocation.")
    token_type: TokenType = Field(
        ..., description="Token discriminator ('access' or 'refresh')."
    )
    exp: int = Field(..., description="Expiration epoch timestamp in seconds.")
    iat: int = Field(..., description="Issued-at epoch timestamp in seconds.")
    nbf: int | None = Field(default=None, description="Not-before epoch timestamp.")
    iss: str = Field(default="Investiga", description="Token issuer name.")
    roles: list[str] = Field(
        default_factory=list, description="Assigned user role names."
    )
    permissions: list[str] = Field(
        default_factory=list, description="Fine-grained permission codes."
    )
    custom_claims: dict[str, Any] = Field(
        default_factory=dict, description="Additional custom domain claims."
    )


class TokenPair(BaseModel):
    """Response contract returning an access and refresh token pair."""

    access_token: str = Field(..., description="Short-lived bearer access token.")
    refresh_token: str = Field(..., description="Long-lived bearer refresh token.")
    token_type: str = Field(default="bearer", description="OAuth2 authorization scheme.")
    expires_in: int = Field(
        ..., description="Access token lifespan remaining in seconds."
    )
