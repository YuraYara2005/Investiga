import apiClient from '@/api/client';
import type {
  ChangePasswordRequest,
  CurrentUserResponse,
  RefreshTokenRequest,
  TokenResponse,
  UpdateProfileRequest,
  UserLoginRequest,
  UserRegisterRequest,
  UserResponse,
} from '@/types/auth';

/**
 * Authentication Service communicating with `/api/v1/auth/*` endpoints.
 */
export const authService = {
  /**
   * Register a new user identity.
   */
  async register(data: UserRegisterRequest): Promise<UserResponse> {
    const response = await apiClient.post<UserResponse>('/api/v1/auth/register', data);
    return response.data;
  },

  /**
   * Authenticate user credentials and retrieve access/refresh JWTs.
   */
  async login(data: UserLoginRequest): Promise<TokenResponse> {
    console.log('LOGIN REQUEST');
    const response = await apiClient.post<TokenResponse>('/api/v1/auth/login', data);
    console.log(response.data);
    return response.data;
  },

  /**
   * Rotate access and refresh token pair.
   */
  async refreshToken(data: RefreshTokenRequest): Promise<TokenResponse> {
    console.log('REFRESH TOKEN REQUEST');
    const response = await apiClient.post<TokenResponse>('/api/v1/auth/refresh', data);
    console.log(response.data);
    return response.data;
  },

  /**
   * Retrieve current authenticated user profile and RBAC permissions.
   */
  async getCurrentUser(): Promise<CurrentUserResponse> {
    console.log('GET CURRENT USER');
    const response = await apiClient.get<CurrentUserResponse>('/api/v1/auth/me');
    console.log('GET CURRENT USER RESPONSE', response.data);
    return response.data;
  },

  /**
   * Update mutable profile fields of authenticated user.
   */
  async updateProfile(data: UpdateProfileRequest): Promise<UserResponse> {
    const response = await apiClient.put<UserResponse>('/api/v1/auth/me', data);
    return response.data;
  },

  /**
   * Rotate account password after re-verifying current password.
   */
  async changePassword(data: ChangePasswordRequest): Promise<void> {
    await apiClient.post('/api/v1/auth/change-password', data);
  },
};
