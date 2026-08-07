import apiClient from '@/api/client';
import type {
  DocumentQueryParams,
  KnowledgeDocumentListResponse,
  KnowledgeDocumentResponse,
  UploadDocumentFormData,
} from '@/types/knowledge';

/**
 * Knowledge Base API Service for document ingestion, search, retrieval, and deletion.
 */
export const knowledgeService = {
  /**
   * Upload and ingest a new knowledge document via multipart/form-data.
   */
  async uploadDocument(
    data: UploadDocumentFormData,
    onProgress?: (progressPercent: number) => void
  ): Promise<KnowledgeDocumentResponse> {
    const formData = new FormData();
    formData.append('file', data.file);
    if (data.title) formData.append('title', data.title);
    if (data.description) formData.append('description', data.description);
    if (data.category) formData.append('category', data.category);
    if (data.language) formData.append('language', data.language);
    if (data.tags && data.tags.length > 0) {
      formData.append('tags', data.tags.join(','));
    }

    const response = await apiClient.post<KnowledgeDocumentResponse>(
      '/api/v1/knowledge/upload',
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        onUploadProgress: (progressEvent) => {
          if (progressEvent.total && onProgress) {
            const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total);
            onProgress(percent);
          }
        },
      }
    );
    return response.data;
  },

  /**
   * Fetch paginated list of knowledge documents with optional filters and sorting.
   */
  async listDocuments(
    params?: DocumentQueryParams,
    signal?: AbortSignal
  ): Promise<KnowledgeDocumentListResponse> {
    const response = await apiClient.get<KnowledgeDocumentListResponse>('/api/v1/knowledge', {
      params,
      signal,
    });
    return response.data;
  },

  /**
   * Fetch single document record by unique UUID.
   */
  async getDocument(id: string, signal?: AbortSignal): Promise<KnowledgeDocumentResponse> {
    const response = await apiClient.get<KnowledgeDocumentResponse>(`/api/v1/knowledge/${id}`, {
      signal,
    });
    return response.data;
  },

  /**
   * Soft-delete knowledge document and remove physical storage.
   */
  async deleteDocument(id: string): Promise<void> {
    await apiClient.delete(`/api/v1/knowledge/${id}`);
  },
};
