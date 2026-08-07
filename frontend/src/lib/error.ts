import { isAxiosError } from 'axios';
import type { ErrorResponse, ParsedApiError } from '@/types/errors';

/**
 * Parse an Axios or generic exception into a normalized ParsedApiError.
 */
export function parseApiError(error: unknown): ParsedApiError {
  if (isAxiosError(error)) {
    const status = error.response?.status ?? 0;
    const data = error.response?.data as ErrorResponse | undefined;

    if (data?.error) {
      return {
        code: data.error.code || 'API_ERROR',
        message: data.error.message || error.message || 'An unexpected API error occurred',
        status,
        details: data.error.details,
        traceId: data.error.trace_id,
      };
    }

    // Fallback for non-standard or network errors
    if (error.code === 'ECONNABORTED') {
      return {
        code: 'TIMEOUT',
        message: 'Request timed out. Please verify connectivity and try again.',
        status: 408,
      };
    }

    if (!error.response) {
      return {
        code: 'NETWORK_ERROR',
        message: 'Network error. Please check your internet connection or server availability.',
        status: 0,
      };
    }

    return {
      code: `HTTP_${status}`,
      message: (error.response.data as { detail?: string })?.detail || error.message || 'Request failed',
      status,
    };
  }

  if (error instanceof Error) {
    return {
      code: 'CLIENT_ERROR',
      message: error.message,
      status: 0,
    };
  }

  return {
    code: 'UNKNOWN_ERROR',
    message: 'An unknown error occurred',
    status: 0,
  };
}
