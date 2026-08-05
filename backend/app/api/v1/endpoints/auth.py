"""Authentication and User Profile HTTP API Endpoints for Investiga.

This module exposes the REST API routes for user registration, Argon2id credential
authentication, JWT token rotation, profile retrieval/mutation, and password updates.
Controllers are strictly decoupled from data persistence and business logic, delegating
all operations directly to the Service Layer (`AuthService`, `UserService`).
"""

from fastapi import APIRouter, Depends, Response, status

from app.api.dependencies import (
    get_auth_service,
    get_current_active_user,
    get_user_service,
)
from app.auth.models import User
from app.auth.schemas.requests import (
    ChangePasswordRequest,
    RefreshTokenRequest,
    UpdateProfileRequest,
    UserLoginRequest,
    UserRegisterRequest,
)
from app.auth.schemas.responses import (
    CurrentUserResponse,
    TokenResponse,
    UserResponse,
)
from app.auth.services import AuthService, UserService
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication & Identity"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register User Account",
    description=(
        "Register a new operational engineer or analyst account. Validates password complexity, "
        "enforces email uniqueness, hashes credentials using Argon2id, and provisions default RBAC roles."
    ),
    responses={
        status.HTTP_201_CREATED: {
            "description": "User account successfully registered and provisioned.",
            "model": UserResponse,
        },
        status.HTTP_400_BAD_REQUEST: {
            "description": "Validation error (e.g. password does not meet corporate complexity requirements).",
        },
        status.HTTP_409_CONFLICT: {
            "description": "Email address is already registered in the platform.",
        },
    },
)
async def register(
    request: UserRegisterRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> UserResponse:
    """Register a new user identity in the platform."""
    return await auth_service.register(request=request)


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="User Credential Authentication",
    description=(
        "Authenticate user credentials via email and password. Issues a cryptographically signed "
        "JWT access token (short-lived) and refresh token (long-lived). Timing-attack resilient."
    ),
    responses={
        status.HTTP_200_OK: {
            "description": "Authentication successful. Returns JWT token pair.",
            "model": TokenResponse,
        },
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Invalid email or password (constant-time generic error).",
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "User account is inactive, disabled, or soft-deleted.",
        },
    },
)
async def login(
    request: UserLoginRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    """Authenticate credentials and issue JWT token pair."""
    return await auth_service.authenticate(request=request)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Rotate Session Tokens",
    description=(
        "Exchange a valid long-lived refresh token for a newly rotated access token and refresh token pair. "
        "Enforces refresh token signature verification, expiration bounds, and principal active status."
    ),
    responses={
        status.HTTP_200_OK: {
            "description": "Tokens successfully rotated. Returns new JWT token pair.",
            "model": TokenResponse,
        },
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Refresh token is expired, forged, or malformed.",
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Associated user account has been disabled or suspended.",
        },
    },
)
async def refresh(
    request: RefreshTokenRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    """Rotate JWT refresh and access token pair."""
    return await auth_service.refresh_access_token(request=request)


@router.get(
    "/me",
    response_model=CurrentUserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Authenticated User Profile",
    description=(
        "Retrieve the profile details, active roles, and aggregated authorization permissions "
        "for the currently authenticated principal resolved from the Bearer JWT access token."
    ),
    responses={
        status.HTTP_200_OK: {
            "description": "Current user identity and aggregated permission claims.",
            "model": CurrentUserResponse,
        },
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Missing, expired, or invalid Bearer access token.",
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Account is disabled, suspended, or soft-deleted.",
        },
    },
)
async def get_current_user_profile(
    current_user: User = Depends(get_current_active_user),
    user_service: UserService = Depends(get_user_service),
) -> CurrentUserResponse:
    """Fetch profile and RBAC entitlements of the authenticated user."""
    return await user_service.get_current_user_profile(user_id=current_user.id)


@router.put(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Authenticated User Profile",
    description=(
        "Update mutable profile fields (such as full name) for the authenticated principal. "
        "Email and authentication credentials cannot be mutated through this route."
    ),
    responses={
        status.HTTP_200_OK: {
            "description": "User profile successfully updated.",
            "model": UserResponse,
        },
        status.HTTP_400_BAD_REQUEST: {
            "description": "Invalid update payload.",
        },
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Missing or invalid Bearer access token.",
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Account is disabled or soft-deleted.",
        },
    },
)
async def update_current_user_profile(
    request: UpdateProfileRequest,
    current_user: User = Depends(get_current_active_user),
    user_service: UserService = Depends(get_user_service),
) -> UserResponse:
    """Update profile information of the authenticated user."""
    return await user_service.update_profile(
        user_id=current_user.id,
        request=request,
    )


@router.post(
    "/change-password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Change Authenticated User Password",
    description=(
        "Rotate account password for the authenticated principal. Requires identity re-verification "
        "via current plaintext password and enforces corporate complexity validation on the new password."
    ),
    responses={
        status.HTTP_204_NO_CONTENT: {
            "description": "Password successfully updated.",
        },
        status.HTTP_400_BAD_REQUEST: {
            "description": "New password fails corporate complexity policies.",
        },
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Current password verification failed or invalid Bearer token.",
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Account is disabled or soft-deleted.",
        },
    },
)
async def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_active_user),
    user_service: UserService = Depends(get_user_service),
) -> Response:
    """Change account password after re-verifying current credentials."""
    await user_service.change_password(
        user_id=current_user.id,
        request=request,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
