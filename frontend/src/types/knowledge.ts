export type DocumentCategory =
  | 'RUNBOOK'
  | 'INCIDENT_REPORT'
  | 'MANUAL'
  | 'CONFIGURATION'
  | 'POLICY'
  | 'OTHER';

export type ProcessingStatus =
  | 'UPLOADED'
  | 'VALIDATING'
  | 'PROCESSING'
  | 'READY'
  | 'FAILED';

export type EmbeddingStatus =
  | 'NOT_STARTED'
  | 'QUEUED'
  | 'EMBEDDED'
  | 'FAILED';

export interface KnowledgeDocumentResponse {
  id: string;
  title: string;
  description: string | null;
  original_filename: string;
  stored_filename: string;
  file_extension: string;
  mime_type: string;
  file_size: number;
  language: string;
  category: DocumentCategory;
  tags: string[];
  version: number;
  checksum: string;
  storage_path: string;
  processing_status: ProcessingStatus;
  embedding_status: EmbeddingStatus;
  uploaded_by: string;
  created_at: string;
  updated_at: string;
  is_deleted: boolean;
  deleted_at: string | null;
}

export interface KnowledgeDocumentListResponse {
  items: KnowledgeDocumentResponse[];
  total: number;
  skip: number;
  limit: number;
}

export interface DocumentQueryParams {
  skip?: number;
  limit?: number;
  category?: DocumentCategory;
  processing_status?: ProcessingStatus;
  embedding_status?: EmbeddingStatus;
  search?: string;
  sort_by?: string;
  sort_desc?: boolean;
}

export interface UploadDocumentFormData {
  file: File;
  title: string;
  description?: string;
  category?: DocumentCategory;
  language?: string;
  tags?: string[];
}
