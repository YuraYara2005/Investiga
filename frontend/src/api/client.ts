import axios, { type AxiosInstance } from 'axios';
import { setupInterceptors } from './interceptors';

/**
 * Enterprise Axios API Client configured with base URL, timeout, and custom interceptors.
 */
export const apiClient: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
    Accept: 'application/json',
  },
});

// Attach request and response interceptors (JWT injection, 401 refresh queue, error parsing)
setupInterceptors(apiClient);

export default apiClient;
