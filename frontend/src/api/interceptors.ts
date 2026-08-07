import type { AxiosError, AxiosInstance, InternalAxiosRequestConfig } from 'axios';
import axios from 'axios';
import { tokenStorage } from '@/auth/tokenStorage';
import type { TokenResponse } from '@/types/auth';

let isRefreshing = false;
let failedQueue: Array<{
  resolve: (token: string) => void;
  reject: (error: unknown) => void;
}> = [];

const processQueue = (error: unknown, token: string | null = null) => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error);
    } else if (token) {
      prom.resolve(token);
    }
  });
  failedQueue = [];
};

/**
 * Configure request and response interceptors on the given Axios instance.
 */
export function setupInterceptors(client: AxiosInstance): void {
  // Request Interceptor: Attach Bearer token and correlation ID
  client.interceptors.request.use(
    (config: InternalAxiosRequestConfig) => {
      console.log('REQUEST', config.url);

      // Inject unique distributed trace / correlation ID
      if (!config.headers['X-Request-ID']) {
        const traceId = `req-${Math.random().toString(36).substring(2, 10)}${Date.now().toString(36)}`;
        config.headers['X-Request-ID'] = traceId;
      }

      const token = tokenStorage.getAccessToken();
      console.log('TOKEN FROM STORAGE', token);
      console.log('HEADERS BEFORE', { ...config.headers });

      // Inject Bearer access token if available
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }

      console.log('HEADERS AFTER', { ...config.headers });

      return config;
    },
    (error) => Promise.reject(error)
  );

  // Response Interceptor: Handle 401 token rotation and retry queue
  client.interceptors.response.use(
    (response) => response,
    async (error: AxiosError) => {
      const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

      // Avoid infinite loop if refresh or login endpoints fail
      const isAuthEndpoint =
        originalRequest?.url?.includes('/auth/login') ||
        originalRequest?.url?.includes('/auth/refresh') ||
        originalRequest?.url?.includes('/auth/register');

      if (error.response?.status === 401 && !originalRequest._retry && !isAuthEndpoint) {
        if (isRefreshing) {
          // If a refresh is already in progress, queue this request until it finishes
          return new Promise((resolve, reject) => {
            failedQueue.push({
              resolve: (newToken: string) => {
                if (originalRequest.headers) {
                  originalRequest.headers.Authorization = `Bearer ${newToken}`;
                }
                resolve(client(originalRequest));
              },
              reject: (err: unknown) => {
                reject(err);
              },
            });
          });
        }

        originalRequest._retry = true;
        isRefreshing = true;

        const refreshToken = tokenStorage.getRefreshToken();
        if (!refreshToken) {
          tokenStorage.clearTokens();
          isRefreshing = false;
          // Notify app or dispatch session expired
          return Promise.reject(error);
        }

        try {
          // Direct axios call to avoid interceptor recursion
          const response = await axios.post<TokenResponse>(
            `${client.defaults.baseURL || ''}/api/v1/auth/refresh`,
            { refresh_token: refreshToken },
            { headers: { 'Content-Type': 'application/json' } }
          );

          const { access_token, refresh_token: newRefreshToken } = response.data;
          tokenStorage.setTokens(access_token, newRefreshToken);

          if (originalRequest.headers) {
            originalRequest.headers.Authorization = `Bearer ${access_token}`;
          }

          processQueue(null, access_token);
          return client(originalRequest);
        } catch (refreshError) {
          processQueue(refreshError, null);
          tokenStorage.clearTokens();
          window.dispatchEvent(new CustomEvent('investiga:session-expired'));
          return Promise.reject(refreshError);
        } finally {
          isRefreshing = false;
        }
      }

      return Promise.reject(error);
    }
  );
}
