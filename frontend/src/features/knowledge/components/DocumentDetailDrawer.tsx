import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Trash2,
  Copy,
  Check,
  Calendar,
  HardDrive,
  User,
  Layers,
  AlertTriangle,
} from 'lucide-react';
import { knowledgeService } from '@/services/knowledgeService';
import { queryKeys } from '@/api/queryKeys';
import { toast } from '@/stores/useNotificationStore';
import { parseApiError } from '@/lib/error';
import { useClipboard } from '@/hooks/useClipboard';
import { formatBytes } from '@/lib/utils';
import { formatDate } from '@/lib/date';
import { Drawer } from '@/components/ui/Drawer';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { Skeleton } from '@/components/ui/Skeleton';
import { CategoryBadge, ProcessingStatusBadge, EmbeddingStatusBadge } from '@/components/ui/StatusBadge';
import { Badge } from '@/components/ui/Badge';
import { CodeBlock } from '@/components/data/CodeBlock';

interface DocumentDetailDrawerProps {
  documentId: string | null;
  isOpen: boolean;
  onClose: () => void;
}

export const DocumentDetailDrawer: React.FC<DocumentDetailDrawerProps> = ({
  documentId,
  isOpen,
  onClose,
}) => {
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const { hasCopied, copy } = useClipboard();
  const queryClient = useQueryClient();

  const {
    data: doc,
    isLoading,
    isError,
    error,
  } = useQuery({
    queryKey: queryKeys.knowledge.detail(documentId || ''),
    queryFn: () => knowledgeService.getDocument(documentId!),
    enabled: !!documentId && isOpen,
  });

  const deleteMutation = useMutation({
    mutationFn: () => knowledgeService.deleteDocument(documentId!),
    onSuccess: () => {
      toast.success('Document Deleted', 'Record soft-deleted and physical storage purged.');
      queryClient.invalidateQueries({ queryKey: queryKeys.knowledge.lists() });
      setIsDeleteModalOpen(false);
      onClose();
    },
    onError: (err) => {
      const parsed = parseApiError(err);
      toast.error('Deletion Failed', parsed.message);
    },
  });

  return (
    <>
      <Drawer
        isOpen={isOpen}
        onClose={onClose}
        title={doc ? doc.title : 'Document Metadata'}
        description={doc ? doc.original_filename : 'Inspecting knowledge item'}
        width="xl"
        footer={
          <div className="flex items-center justify-between w-full">
            <Button
              variant="danger"
              size="sm"
              onClick={() => setIsDeleteModalOpen(true)}
              leftIcon={<Trash2 className="h-3.5 w-3.5" />}
              disabled={isLoading || !doc}
            >
              Delete Document
            </Button>
            <Button variant="outline" size="sm" onClick={onClose}>
              Close Inspector
            </Button>
          </div>
        }
      >
        {isLoading ? (
          <div className="space-y-4">
            <Skeleton className="h-20 w-full" />
            <Skeleton className="h-40 w-full" />
            <Skeleton className="h-28 w-full" />
          </div>
        ) : isError || !doc ? (
          <div className="py-12 text-center text-xs text-destructive">
            {parseApiError(error).message || 'Failed to load document details.'}
          </div>
        ) : (
          <div className="space-y-6">
            {/* Status Header */}
            <div className="flex flex-wrap items-center gap-2 p-3 rounded-lg border border-border/60 bg-muted/20">
              <CategoryBadge category={doc.category} />
              <ProcessingStatusBadge status={doc.processing_status} />
              <EmbeddingStatusBadge status={doc.embedding_status} />
              <Badge variant="secondary" className="font-mono">
                v{doc.version}
              </Badge>
            </div>

            {/* Description */}
            {doc.description && (
              <div className="space-y-1">
                <h4 className="text-xs font-semibold text-foreground uppercase tracking-wider">
                  Description / Overview
                </h4>
                <p className="text-xs text-muted-foreground leading-relaxed p-3 rounded-lg bg-card border border-border/60">
                  {doc.description}
                </p>
              </div>
            )}

            {/* Tags */}
            {doc.tags && doc.tags.length > 0 && (
              <div className="space-y-1.5">
                <h4 className="text-xs font-semibold text-foreground uppercase tracking-wider">
                  Operational Tags
                </h4>
                <div className="flex flex-wrap gap-1.5">
                  {doc.tags.map((tag, idx) => (
                    <span
                      key={idx}
                      className="px-2 py-0.5 rounded-md bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 text-xs font-mono"
                    >
                      #{tag}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Technical Metadata Grid */}
            <div className="space-y-2">
              <h4 className="text-xs font-semibold text-foreground uppercase tracking-wider">
                Technical Specifications
              </h4>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                <div className="p-3 rounded-lg border border-border/60 bg-card space-y-1">
                  <span className="text-muted-foreground flex items-center gap-1.5 text-[11px]">
                    <HardDrive className="h-3 w-3" /> File Size & Type
                  </span>
                  <p className="font-semibold text-foreground font-mono">
                    {formatBytes(doc.file_size)} • {doc.file_extension.toUpperCase()}
                  </p>
                  <p className="text-[10px] text-muted-foreground font-mono truncate">
                    {doc.mime_type}
                  </p>
                </div>

                <div className="p-3 rounded-lg border border-border/60 bg-card space-y-1">
                  <span className="text-muted-foreground flex items-center gap-1.5 text-[11px]">
                    <Calendar className="h-3 w-3" /> Timeline
                  </span>
                  <p className="font-semibold text-foreground font-mono">
                    {formatDate(doc.created_at)}
                  </p>
                  <p className="text-[10px] text-muted-foreground">
                    Updated: {formatDate(doc.updated_at)}
                  </p>
                </div>

                <div className="p-3 rounded-lg border border-border/60 bg-card space-y-1">
                  <span className="text-muted-foreground flex items-center gap-1.5 text-[11px]">
                    <User className="h-3 w-3" /> Ingestion Author
                  </span>
                  <p className="font-mono text-[11px] text-foreground truncate">
                    {doc.uploaded_by}
                  </p>
                  <p className="text-[10px] text-muted-foreground">Language: {doc.language}</p>
                </div>

                <div className="p-3 rounded-lg border border-border/60 bg-card space-y-1">
                  <span className="text-muted-foreground flex items-center gap-1.5 text-[11px]">
                    <Layers className="h-3 w-3" /> Storage Key
                  </span>
                  <p className="font-mono text-[11px] text-foreground truncate">
                    {doc.stored_filename}
                  </p>
                  <p className="text-[10px] text-muted-foreground font-mono truncate">
                    {doc.storage_path}
                  </p>
                </div>
              </div>
            </div>

            {/* Checksum Hash */}
            <div className="space-y-1">
              <div className="flex items-center justify-between">
                <h4 className="text-xs font-semibold text-foreground uppercase tracking-wider">
                  SHA-256 Cryptographic Checksum
                </h4>
                <button
                  type="button"
                  onClick={() => copy(doc.checksum)}
                  className="text-xs text-primary hover:underline flex items-center gap-1"
                >
                  {hasCopied ? (
                    <>
                      <Check className="h-3 w-3 text-emerald-400" />
                      <span className="text-emerald-400">Copied</span>
                    </>
                  ) : (
                    <>
                      <Copy className="h-3 w-3" />
                      <span>Copy Hash</span>
                    </>
                  )}
                </button>
              </div>
              <div className="p-2.5 rounded bg-slate-950 border border-slate-800 font-mono text-[11px] text-cyan-300 break-all">
                {doc.checksum}
              </div>
            </div>

            {/* Raw JSON Record Inspector */}
            <div className="space-y-1">
              <h4 className="text-xs font-semibold text-foreground uppercase tracking-wider">
                Raw Record JSON
              </h4>
              <CodeBlock code={JSON.stringify(doc, null, 2)} language="json" maxHeight="max-h-60" />
            </div>
          </div>
        )}
      </Drawer>

      {/* Deletion Confirmation Modal */}
      <Modal
        isOpen={isDeleteModalOpen}
        onClose={() => setIsDeleteModalOpen(false)}
        title="Delete Knowledge Document"
        maxWidth="md"
      >
        <div className="space-y-4">
          <div className="flex items-start gap-3 p-3 rounded-lg bg-destructive/10 border border-destructive/30 text-destructive text-xs">
            <AlertTriangle className="h-5 w-5 flex-shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold">Permanent Storage Purge</p>
              <p className="mt-0.5 text-muted-foreground">
                This action will mark the document as deleted in the database and immediately purge the physical file from the cluster storage backend.
              </p>
            </div>
          </div>

          <p className="text-xs text-foreground">
            Are you sure you want to delete <strong className="font-semibold">{doc?.title}</strong>?
          </p>

          <div className="flex items-center justify-end gap-3 pt-3 border-t border-border/40">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setIsDeleteModalOpen(false)}
              disabled={deleteMutation.isPending}
            >
              Cancel
            </Button>
            <Button
              variant="danger"
              size="sm"
              isLoading={deleteMutation.isPending}
              onClick={() => deleteMutation.mutate()}
            >
              Confirm Deletion
            </Button>
          </div>
        </div>
      </Modal>
    </>
  );
};
