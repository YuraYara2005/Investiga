import { describe, it, expect } from 'vitest';
import { parseApiError } from './error';

describe('error.ts', () => {
  it('parses standard JS errors', () => {
    const error = new Error('Database connection failed');
    const parsed = parseApiError(error);
    expect(parsed.code).toBe('CLIENT_ERROR');
    expect(parsed.message).toBe('Database connection failed');
    expect(parsed.status).toBe(0);
  });

  it('parses unknown exceptions with safe fallback', () => {
    const parsed = parseApiError('string error');
    expect(parsed.code).toBe('UNKNOWN_ERROR');
    expect(parsed.message).toBe('An unknown error occurred');
  });
});
