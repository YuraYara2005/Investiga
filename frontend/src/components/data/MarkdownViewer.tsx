import React from 'react';
import { cn } from '@/lib/utils';

export interface MarkdownViewerProps {
  content: string;
  className?: string;
}

export const MarkdownViewer: React.FC<MarkdownViewerProps> = ({ content, className }) => {
  // Simple clean markdown parser for headings, lists, bold, code, quotes
  const renderParagraphs = () => {
    const lines = content.split('\n');
    return lines.map((line, idx) => {
      const trimmed = line.trim();
      if (trimmed.startsWith('### ')) {
        return (
          <h3 key={idx} className="text-sm font-bold text-foreground mt-4 mb-2">
            {trimmed.replace('### ', '')}
          </h3>
        );
      }
      if (trimmed.startsWith('## ')) {
        return (
          <h2 key={idx} className="text-base font-bold text-foreground mt-5 mb-2 pb-1 border-b border-border/40">
            {trimmed.replace('## ', '')}
          </h2>
        );
      }
      if (trimmed.startsWith('# ')) {
        return (
          <h1 key={idx} className="text-lg font-bold text-foreground mt-6 mb-3">
            {trimmed.replace('# ', '')}
          </h1>
        );
      }
      if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
        return (
          <li key={idx} className="text-xs text-muted-foreground ml-4 list-disc my-1">
            {trimmed.substring(2)}
          </li>
        );
      }
      if (trimmed.startsWith('> ')) {
        return (
          <blockquote key={idx} className="border-l-2 border-primary/60 pl-3 py-1 my-2 text-xs italic text-muted-foreground bg-muted/20 rounded-r">
            {trimmed.substring(2)}
          </blockquote>
        );
      }
      if (trimmed === '') {
        return <div key={idx} className="h-2" />;
      }
      return (
        <p key={idx} className="text-xs text-muted-foreground leading-relaxed my-1">
          {line}
        </p>
      );
    });
  };

  return (
    <div className={cn('prose prose-sm dark:prose-invert max-w-none text-xs', className)}>
      {renderParagraphs()}
    </div>
  );
};
