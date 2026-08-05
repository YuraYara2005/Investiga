"""Schemas package initialization for Identity and Authentication."""

from app.auth.schemas.requests import (
    ChangePasswordRequest,
    RefreshTokenRequest,
    UpdateProfileRequest,
    UserLoginRequest,
    UserRegisterRequest,
)
from app.auth.schemas.responses import (
    CurrentUserResponse,
    PermissionResponse,
    RoleResponse,
    TokenResponse,
    UserResponse,
)

__all__ = [
    "ChangePasswordRequest",
    "CurrentUserResponse",
    "PermissionResponse",
    "RefreshTokenRequest",
    "RoleResponse",
    "TokenResponse",
    "UpdateProfileRequest",
    "UserLoginRequest",
    "UserRegisterRequest",
    "UserResponse",
]
