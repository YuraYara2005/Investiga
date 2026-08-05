"""Authentication and Identity domain package for Investiga."""

from app.auth.models import (
    Permission,
    Role,
    User,
    role_permissions,
    user_roles,
)
from app.auth.repositories import (
    BaseRepository,
    IBaseRepository,
    IPermissionRepository,
    IRoleRepository,
    IUserRepository,
    PermissionRepository,
    RoleRepository,
    UserRepository,
)
from app.auth.schemas import (
    ChangePasswordRequest,
    CurrentUserResponse,
    PermissionResponse,
    RefreshTokenRequest,
    RoleResponse,
    TokenResponse,
    UpdateProfileRequest,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from app.auth.services import (
    AuthService,
    IdentityValidators,
    PasswordPolicy,
    TokenService,
    UserService,
    default_password_policy,
)

__all__ = [
    "AuthService",
    "BaseRepository",
    "ChangePasswordRequest",
    "CurrentUserResponse",
    "IBaseRepository",
    "IPermissionRepository",
    "IRoleRepository",
    "IUserRepository",
    "IdentityValidators",
    "PasswordPolicy",
    "Permission",
    "PermissionRepository",
    "PermissionResponse",
    "RefreshTokenRequest",
    "Role",
    "RoleRepository",
    "RoleResponse",
    "TokenResponse",
    "TokenService",
    "UpdateProfileRequest",
    "User",
    "UserLoginRequest",
    "UserRegisterRequest",
    "UserRepository",
    "UserResponse",
    "UserService",
    "default_password_policy",
    "role_permissions",
    "user_roles",
]


