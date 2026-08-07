export interface ErrorDetail {
  code: string;
  message: string;
  details?: Record<string, unknown>;
  trace_id?: string | null;
  timestamp: string;
}

export interface ErrorResponse {
  success: boolean;
  error: ErrorDetail;
}

export interface ParsedApiError {
  code: string;
  message: string;
  status: number;
  details?: Record<string, unknown>;
  traceId?: string | null;
}
