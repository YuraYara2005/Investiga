import { describe, it, expect, beforeEach } from 'vitest';
import { tokenStorage } from './tokenStorage';

describe('tokenStorage', () => {
  beforeEach(() => {
    localStorage.clear();
    tokenStorage.clearTokens();
  });

  it('stores and retrieves access and refresh tokens', () => {
    expect(tokenStorage.getAccessToken()).toBeNull();
    expect(tokenStorage.getRefreshToken()).toBeNull();
    expect(tokenStorage.hasTokens()).toBe(false);

    tokenStorage.setTokens('access-jwt-123', 'refresh-jwt-456');

    expect(tokenStorage.getAccessToken()).toBe('access-jwt-123');
    expect(tokenStorage.getRefreshToken()).toBe('refresh-jwt-456');
    expect(tokenStorage.hasTokens()).toBe(true);
  });

  it('clears tokens properly', () => {
    tokenStorage.setTokens('access-jwt-123', 'refresh-jwt-456');
    tokenStorage.clearTokens();

    expect(tokenStorage.getAccessToken()).toBeNull();
    expect(tokenStorage.getRefreshToken()).toBeNull();
    expect(tokenStorage.hasTokens()).toBe(false);
  });
});
