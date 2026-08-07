import { format, formatDistanceToNow, parseISO } from 'date-fns';

/**
 * Format ISO 8601 UTC date string into standard enterprise date representation.
 */
export function formatDate(
  isoDate: string | Date | null | undefined,
  pattern: string = 'MMM dd, yyyy HH:mm:ss'
): string {
  if (!isoDate) return '—';
  try {
    const date = typeof isoDate === 'string' ? parseISO(isoDate) : isoDate;
    if (isNaN(date.getTime())) return '—';
    return format(date, pattern);
  } catch {
    return '—';
  }
}

/**
 * Format relative time distance from current moment (e.g. "5 minutes ago").
 */
export function formatRelativeTime(isoDate: string | Date | null | undefined): string {
  if (!isoDate) return '—';
  try {
    const date = typeof isoDate === 'string' ? parseISO(isoDate) : isoDate;
    if (isNaN(date.getTime())) return '—';
    return formatDistanceToNow(date, { addSuffix: true });
  } catch {
    return '—';
  }
}
