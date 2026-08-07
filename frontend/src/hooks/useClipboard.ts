import { useState, useCallback } from 'react';

/**
 * Hook to copy text to clipboard with a brief copied indicator state.
 */
export function useClipboard(timeoutMs: number = 2000) {
  const [hasCopied, setHasCopied] = useState(false);

  const copy = useCallback(
    async (text: string) => {
      try {
        await navigator.clipboard.writeText(text);
        setHasCopied(true);
        setTimeout(() => setHasCopied(false), timeoutMs);
        return true;
      } catch {
        setHasCopied(false);
        return false;
      }
    },
    [timeoutMs]
  );

  return { hasCopied, copy };
}
