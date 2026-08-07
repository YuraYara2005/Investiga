import React, { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  BookOpen,
  UploadCloud,
  Search,
  RefreshCw,
  Eye,
  FileText,
} from 'lucide-react';
import { knowledgeService } from '@/services/knowledgeService';
import { queryKeys } from '@/api/queryKeys';
import { useDebounce } from '@/hooks/useDebounce';
import { formatBytes } from '@/lib/utils';
import { formatDate } from '@/lib/date';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { Card } from '@/components/ui/Card';
import { Table, TableHeader, TableBody, TableHead, TableRow, TableCell } from '@/components/ui/Table';
import { CategoryBadge, ProcessingStatusBadge, EmbeddingStatusBadge } from '@/components/ui/StatusBadge';
import { Pagination } from '@/components/navigation/Pagination';
import { EmptyState } from '@/components/feedback/EmptyState';
import { ErrorState } from '@/components/feedback/ErrorState';
import { Skeleton } from '@/components/ui/Skeleton';
import { DocumentUploadModal } from '../components/DocumentUploadModal';
import { DocumentDetailDrawer } from '../components/DocumentDetailDrawer';
import type { DocumentCategory, ProcessingStatus } from '@/types/knowledge';

export const KnowledgeListPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();

  // Search & Filter State
  const [searchTerm, setSearchTerm] = useState<string>('');
  const debouncedSearch = useDebounce(searchTerm, 300);
  const [selectedCategory, setSelectedCategory] = useState<string>('ALL');
  const [selectedStatus, setSelectedStatus] = useState<string>('ALL');
  const [sortBy, setSortBy] = useState<string>('created_at');
  const [sortDesc, setSortDesc] = useState<boolean>(true);

  // Pagination State
  const [skip, setSkip] = useState<number>(0);
  const [limit, setLimit] = useState<number>(25);

  // Modals & Drawers
  const [isUploadModalOpen, setIsUploadModalOpen] = useState<boolean>(false);
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);
  const [isDrawerOpen, setIsDrawerOpen] = useState<boolean>(false);

  // Read URL search params on mount
  useEffect(() => {
    if (searchParams.get('action') === 'upload') {
      setIsUploadModalOpen(true);
      searchParams.delete('action');
      setSearchParams(searchParams, { replace: true });
    }
    const docId = searchParams.get('doc');
    if (docId) {
      setSelectedDocId(docId);
      setIsDrawerOpen(true);
    }
  }, [searchParams, setSearchParams]);

  // Query Params
  const queryParams = {
    skip,
    limit,
    search: debouncedSearch.trim() ? debouncedSearch.trim() : undefined,
    category: selectedCategory !== 'ALL' ? (selectedCategory as DocumentCategory) : undefined,
    processing_status: selectedStatus !== 'ALL' ? (selectedStatus as ProcessingStatus) : undefined,
    sort_by: sortBy,
    sort_desc: sortDesc,
  };

  const {
    data,
    isLoading,
    isError,
    refetch,
    isFetching,
  } = useQuery({
    queryKey: queryKeys.knowledge.list(queryParams),
    queryFn: ({ signal }) => knowledgeService.listDocuments(queryParams, signal),
  });

  const handleOpenDoc = (id: string) => {
    setSelectedDocId(id);
    setIsDrawerOpen(true);
  };

  const categoryFilterOptions = [
    { value: 'ALL', label: 'All Categories' },
    { value: 'RUNBOOK', label: 'Runbook' },
    { value: 'INCIDENT_REPORT', label: 'Incident Report' },
    { value: 'MANUAL', label: 'Manual' },
    { value: 'CONFIGURATION', label: 'Configuration' },
    { value: 'POLICY', label: 'Policy' },
    { value: 'OTHER', label: 'Other' },
  ];

  const statusFilterOptions = [
    { value: 'ALL', label: 'All Statuses' },
    { value: 'READY', label: 'Ready' },
    { value: 'PROCESSING', label: 'Processing' },
    { value: 'VALIDATING', label: 'Validating' },
    { value: 'UPLOADED', label: 'Uploaded' },
    { value: 'FAILED', label: 'Failed' },
  ];

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-border/40">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-foreground sm:text-2xl flex items-center gap-2">
            <BookOpen className="h-6 w-6 text-cyan-400" />
            Knowledge Base
          </h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            Operational documentation, runbooks, and incident post-mortems indexed for reasoning.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => refetch()}
            isLoading={isFetching}
            leftIcon={<RefreshCw className="h-3.5 w-3.5" />}
          >
            Refresh
          </Button>

          <Button
            variant="primary"
            size="sm"
            onClick={() => setIsUploadModalOpen(true)}
            leftIcon={<UploadCloud className="h-3.5 w-3.5" />}
          >
            Upload Runbook
          </Button>
        </div>
      </div>

      {/* Filter & Search Bar */}
      <Card className="p-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {/* Search Input */}
          <div className="relative">
            <Input
              placeholder="Search title, filename, description..."
              value={searchTerm}
              onChange={(e) => {
                setSearchTerm(e.target.value);
                setSkip(0);
              }}
              leftIcon={<Search className="h-4 w-4" />}
            />
          </div>

          {/* Category Filter */}
          <div>
            <Select
              options={categoryFilterOptions}
              value={selectedCategory}
              onChange={(e) => {
                setSelectedCategory(e.target.value);
                setSkip(0);
              }}
            />
          </div>

          {/* Status Filter */}
          <div>
            <Select
              options={statusFilterOptions}
              value={selectedStatus}
              onChange={(e) => {
                setSelectedStatus(e.target.value);
                setSkip(0);
              }}
            />
          </div>

          {/* Sort By Filter */}
          <div className="flex items-center gap-2">
            <Select
              options={[
                { value: 'created_at', label: 'Date Created' },
                { value: 'title', label: 'Document Title' },
                { value: 'file_size', label: 'File Size' },
              ]}
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              className="flex-1"
            />
            <Button
              variant="outline"
              size="icon"
              onClick={() => setSortDesc(!sortDesc)}
              title={sortDesc ? 'Descending Order' : 'Ascending Order'}
              className="font-mono text-xs"
            >
              {sortDesc ? '↓' : '↑'}
            </Button>
          </div>
        </div>
      </Card>

      {/* Data Table View */}
      {isError ? (
        <ErrorState
          title="Failed to Load Knowledge Base"
          message="Could not retrieve documents from cluster API."
          onRetry={() => refetch()}
        />
      ) : (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[320px]">Document</TableHead>
                  <TableHead>Category</TableHead>
                  <TableHead>Processing</TableHead>
                  <TableHead>Embedding</TableHead>
                  <TableHead>Size</TableHead>
                  <TableHead>Ingested</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>

              <TableBody>
                {isLoading ? (
                  Array.from({ length: 5 }).map((_, idx) => (
                    <TableRow key={idx}>
                      <TableCell>
                        <Skeleton className="h-5 w-48 mb-1" />
                        <Skeleton className="h-3 w-32" />
                      </TableCell>
                      <TableCell><Skeleton className="h-6 w-20" /></TableCell>
                      <TableCell><Skeleton className="h-6 w-20" /></TableCell>
                      <TableCell><Skeleton className="h-6 w-20" /></TableCell>
                      <TableCell><Skeleton className="h-4 w-12" /></TableCell>
                      <TableCell><Skeleton className="h-4 w-24" /></TableCell>
                      <TableCell className="text-right"><Skeleton className="h-8 w-16 ml-auto" /></TableCell>
                    </TableRow>
                  ))
                ) : !data?.items || data.items.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={7} className="h-48 text-center">
                      <EmptyState
                        icon={<FileText className="h-8 w-8 text-muted-foreground" />}
                        title="No Documents Found"
                        description={
                          searchTerm || selectedCategory !== 'ALL' || selectedStatus !== 'ALL'
                            ? 'No knowledge items match your current filter parameters.'
                            : 'Get started by uploading operational runbooks and post-mortems.'
                        }
                        actionLabel={
                          searchTerm || selectedCategory !== 'ALL'
                            ? 'Clear Filters'
                            : 'Upload Runbook'
                        }
                        onAction={
                          searchTerm || selectedCategory !== 'ALL'
                            ? () => {
                                setSearchTerm('');
                                setSelectedCategory('ALL');
                                setSelectedStatus('ALL');
                              }
                            : () => setIsUploadModalOpen(true)
                        }
                      />
                    </TableCell>
                  </TableRow>
                ) : (
                  data.items.map((doc) => (
                    <TableRow
                      key={doc.id}
                      onClick={() => handleOpenDoc(doc.id)}
                      className="cursor-pointer hover:bg-muted/40 transition-colors"
                    >
                      <TableCell>
                        <div className="space-y-0.5">
                          <p className="font-semibold text-foreground text-xs hover:text-primary transition-colors">
                            {doc.title}
                          </p>
                          <p className="text-[11px] text-muted-foreground font-mono truncate max-w-xs">
                            {doc.original_filename}
                          </p>
                        </div>
                      </TableCell>

                      <TableCell>
                        <CategoryBadge category={doc.category} />
                      </TableCell>

                      <TableCell>
                        <ProcessingStatusBadge status={doc.processing_status} />
                      </TableCell>

                      <TableCell>
                        <EmbeddingStatusBadge status={doc.embedding_status} />
                      </TableCell>

                      <TableCell className="font-mono text-xs">
                        {formatBytes(doc.file_size)}
                      </TableCell>

                      <TableCell className="font-mono text-xs text-muted-foreground">
                        {formatDate(doc.created_at, 'MMM dd, yyyy')}
                      </TableCell>

                      <TableCell className="text-right">
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleOpenDoc(doc.id);
                          }}
                          aria-label="Inspect document details"
                        >
                          <Eye className="h-4 w-4 text-muted-foreground hover:text-foreground" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>

          {/* Pagination Footer */}
          {data && data.total > 0 && (
            <Pagination
              total={data.total}
              skip={skip}
              limit={limit}
              onPageChange={(newSkip) => setSkip(newSkip)}
              onLimitChange={(newLimit) => {
                setLimit(newLimit);
                setSkip(0);
              }}
            />
          )}
        </Card>
      )}

      {/* Upload Modal */}
      <DocumentUploadModal
        isOpen={isUploadModalOpen}
        onClose={() => setIsUploadModalOpen(false)}
      />

      {/* Document Detail Inspector Drawer */}
      <DocumentDetailDrawer
        documentId={selectedDocId}
        isOpen={isDrawerOpen}
        onClose={() => {
          setIsDrawerOpen(false);
          setSelectedDocId(null);
        }}
      />
    </div>
  );
};
