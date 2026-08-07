const ACCESS_TOKEN_KEY = 'investiga_access_token';
const REFRESH_TOKEN_KEY = 'investiga_refresh_token';

let inMemoryAccessToken: string | null = null;

export const tokenStorage = {
  getAccessToken(): string | null {
    console.log('getAccessToken()');
    if (inMemoryAccessToken) {
      console.log('getAccessToken returning in-memory:', inMemoryAccessToken);
      return inMemoryAccessToken;
    }
    const stored = localStorage.getItem(ACCESS_TOKEN_KEY);
    if (stored) {
      inMemoryAccessToken = stored;
    }
    console.log('getAccessToken returning stored:', stored);
    return stored;
  },

  setAccessToken(token: string | null): void {
    console.log('setAccessToken', token);
    inMemoryAccessToken = token;
    if (token) {
      localStorage.setItem(ACCESS_TOKEN_KEY, token);
    } else {
      localStorage.removeItem(ACCESS_TOKEN_KEY);
    }
    console.log(
      'Stored:',
      localStorage.getItem('investiga_access_token')
    );
  },

  getRefreshToken(): string | null {
    console.log('getRefreshToken()');
    const stored = localStorage.getItem(REFRESH_TOKEN_KEY);
    console.log('getRefreshToken returning:', stored);
    return stored;
  },

  setRefreshToken(token: string | null): void {
    console.log('setRefreshToken', token);
    if (token) {
      localStorage.setItem(REFRESH_TOKEN_KEY, token);
    } else {
      localStorage.removeItem(REFRESH_TOKEN_KEY);
    }
    console.log(
      'Stored refresh:',
      localStorage.getItem('investiga_refresh_token')
    );
  },

  setTokens(accessToken: string, refreshToken: string): void {
    console.log('setTokens()', { accessToken, refreshToken });
    this.setAccessToken(accessToken);
    this.setRefreshToken(refreshToken);
    console.log('Stored access after setTokens:', localStorage.getItem('investiga_access_token'));
  },

  clearTokens(): void {
    console.log('clearTokens()');
    inMemoryAccessToken = null;
    localStorage.removeItem(ACCESS_TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
  },

  hasTokens(): boolean {
    console.log('hasTokens()');
    return !!(this.getAccessToken() || this.getRefreshToken());
  },
};
