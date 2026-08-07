import React from 'react';
import { Copy, Check } from 'lucide-react';
import { useClipboard } from '@/hooks/useClipboard';
import { cn } from '@/lib/utils';

export interface CodeBlockProps {
  code: string;
  language?: string;
  className?: string;
  maxHeight?: string;
}

export const CodeBlock: React.FC<CodeBlockProps> = ({
  code,
  language = 'json',
  className,
  maxHeight = 'max-h-96',
}) => {
  const { hasCopied, copy } = useClipboard();

  return (
    <div className={cn('relative rounded-lg border border-border/80 bg-slate-950 font-mono text-xs overflow-hidden', className)}>
      <div className="flex items-center justify-between px-3 py-1.5 bg-slate-900 border-b border-slate-800 text-[11px] text-slate-400">
        <span className="uppercase font-semibold tracking-wider">{language}</span>
        <button
          type="button"
          onClick={() => copy(code)}
          className="flex items-center gap-1 text-slate-400 hover:text-slate-200 transition-colors p-1 rounded"
          aria-label="Copy code to clipboard"
        >
          {hasCopied ? (
            <>
              <Check className="h-3.5 w-3.5 text-emerald-400" />
              <span className="text-[10px] text-emerald-400 font-sans">Copied</span>
            </>
          ) : (
            <>
              <Copy className="h-3.5 w-3.5" />
              <span className="text-[10px] font-sans">Copy</span>
            </>
          )}
        </button>
      </div>

      <pre className={cn('p-4 overflow-x-auto text-slate-200 leading-relaxed tabular-nums', maxHeight)}>
        <code>{code}</code>
      </pre>
    </div>
  );
};
