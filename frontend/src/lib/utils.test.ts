import { describe, it, expect } from 'vitest';
import { cn, formatBytes, formatLatency, truncateHash } from './utils';

describe('utils.ts', () => {
  it('merges class names with precedence correctly', () => {
    const isHidden = false;
    const result = cn('bg-red-500', 'bg-blue-500', isHidden && 'hidden', 'text-white');
    expect(result).toBe('bg-blue-500 text-white');
  });

  it('formats byte sizes into human readable units', () => {
    expect(formatBytes(0)).toBe('0 B');
    expect(formatBytes(1024)).toBe('1 KB');
    expect(formatBytes(1048576)).toBe('1 MB');
    expect(formatBytes(5242880)).toBe('5 MB');
  });

  it('formats latency probes correctly', () => {
    expect(formatLatency(null)).toBe('N/A');
    expect(formatLatency(undefined)).toBe('N/A');
    expect(formatLatency(0.4)).toBe('< 1 ms');
    expect(formatLatency(14.234)).toBe('14.2 ms');
  });

  it('truncates hashes with ellipsis', () => {
    const hash = 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855';
    expect(truncateHash(hash, 8, 6)).toBe('e3b0c442...52b855');
  });
});
