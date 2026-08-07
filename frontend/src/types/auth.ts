export interface UserResponse {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
  is_verified: boolean;
  is_superuser: boolean;
  roles: string[];
  created_at: string;
  last_login_at: string | null;
}

export interface CurrentUserResponse {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
  is_verified: boolean;
  is_superuser: boolean;
  roles: string[];
  permissions: string[];
  created_at: string;
  last_login_at: string | null;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface UserRegisterRequest {
  email: string;
  password: string;
  full_name: string;
}

export interface UserLoginRequest {
  email: string;
  password: string;
}

export interface RefreshTokenRequest {
  refresh_token: string;
}

export interface UpdateProfileRequest {
  full_name?: string;
}

export interface ChangePasswordRequest {
  current_password: string;
  new_password: string;
}

export interface RoleResponse {
  id: string;
  name: string;
  display_name: string;
  description: string | null;
  is_system_role: boolean;
}

export interface PermissionResponse {
  id: string;
  code: string;
  resource: string;
  action: string;
  description: string | null;
}
