import React, { useRef, useState } from 'react';
import { UploadCloud, FileText, X } from 'lucide-react';
import { cn, formatBytes } from '@/lib/utils';
import { Button } from '@/components/ui/Button';

export interface FileDropzoneProps {
  onFileSelect: (file: File) => void;
  selectedFile: File | null;
  onClear: () => void;
  accept?: string;
  maxSizeBytes?: number; // default 50MB
  error?: string;
}

export const FileDropzone: React.FC<FileDropzoneProps> = ({
  onFileSelect,
  selectedFile,
  onClear,
  accept = '.pdf,.docx,.txt,.md,.html,.json,.log',
  maxSizeBytes = 52428800, // 50MB
  error,
}) => {
  const [isDragOver, setIsDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = () => {
    setIsDragOver(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const file = e.dataTransfer.files[0];
      if (file.size <= maxSizeBytes) {
        onFileSelect(file);
      }
    }
  };

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      if (file.size <= maxSizeBytes) {
        onFileSelect(file);
      }
    }
  };

  if (selectedFile) {
    return (
      <div className="flex items-center justify-between p-3.5 rounded-lg border border-primary/30 bg-primary/5 text-foreground">
        <div className="flex items-center gap-3 min-w-0">
          <div className="h-9 w-9 rounded-md bg-primary/10 text-primary flex items-center justify-center flex-shrink-0">
            <FileText className="h-5 w-5" />
          </div>
          <div className="min-w-0">
            <p className="text-xs font-semibold truncate tracking-tight">{selectedFile.name}</p>
            <p className="text-[11px] text-muted-foreground">{formatBytes(selectedFile.size)}</p>
          </div>
        </div>
        <Button
          type="button"
          variant="ghost"
          size="icon-sm"
          onClick={onClear}
          className="text-muted-foreground hover:text-foreground flex-shrink-0"
          aria-label="Remove selected file"
        >
          <X className="h-4 w-4" />
        </Button>
      </div>
    );
  }

  return (
    <div
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      onClick={() => inputRef.current?.click()}
      className={cn(
        'flex flex-col items-center justify-center p-6 sm:p-8 rounded-xl border-2 border-dashed transition-all cursor-pointer text-center',
        isDragOver
          ? 'border-cyan-400 bg-cyan-500/10'
          : 'border-border/80 hover:border-primary/60 hover:bg-card/60 bg-card/20',
        error && 'border-destructive'
      )}
    >
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        onChange={handleFileInput}
        className="hidden"
      />
      <div className="h-10 w-10 rounded-full bg-primary/10 text-primary flex items-center justify-center mb-3">
        <UploadCloud className="h-5 w-5" />
      </div>
      <p className="text-xs font-semibold text-foreground tracking-tight">
        Click to upload or drag and drop document
      </p>
      <p className="text-[11px] text-muted-foreground mt-1">
        PDF, DOCX, TXT, MD, HTML, JSON, LOG up to {formatBytes(maxSizeBytes)}
      </p>
      {error && <p className="text-[11px] font-medium text-destructive mt-2">{error}</p>}
    </div>
  );
};
