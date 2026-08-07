import { useEffect } from 'react';

interface ShortcutOptions {
  metaKey?: boolean; // Command on macOS / Windows key
  ctrlKey?: boolean; // Control key
  altKey?: boolean; // Alt / Option key
  shiftKey?: boolean; // Shift key
  preventDefault?: boolean;
}

/**
 * Hook to bind a callback to a keyboard key shortcut combination.
 */
export function useKeyboardShortcut(
  key: string,
  callback: (e: KeyboardEvent) => void,
  options: ShortcutOptions = {}
): void {
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      const isKeyMatch = event.key.toLowerCase() === key.toLowerCase();
      const isMetaMatch = options.metaKey ? event.metaKey || event.ctrlKey : true;
      const isCtrlMatch = options.ctrlKey ? event.ctrlKey : true;
      const isAltMatch = options.altKey ? event.altKey : true;
      const isShiftMatch = options.shiftKey ? event.shiftKey : true;

      if (isKeyMatch && isMetaMatch && isCtrlMatch && isAltMatch && isShiftMatch) {
        if (options.preventDefault !== false) {
          event.preventDefault();
        }
        callback(event);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [key, callback, options]);
}
