/**
 * GT 2.0 Document & RAG Service
 * 
 * API client for document upload, processing, and RAG dataset management
 * with real-time progress tracking and comprehensive error handling.
 */

import { api } from './api';
import { getTenantInfo } from './auth';

export type DocumentStatus = 'uploading' | 'processing' | 'completed' | 'failed' | 'pending';
export type DocumentType = 'pdf' | 'docx' | 'txt' | 'md' | 'csv' | 'xlsx' | 'pptx' | 'html' | 'json';

export interface Document {
  id: string;
  name: string;
  filename: string;
  original_filename: string;
  file_path: string;
  file_type: string;
  file_extension: string;
  file_size_bytes: number;
  uploaded_by: string;
  processing_status: DocumentStatus;
  chunk_count?: number;
  vector_count?: number;
  error_details?: any;
  created_at: string;
  updated_at?: string;
  chunks_processed?: number;
  total_chunks_expected?: number;
  processing_progress?: number;
  processing_stage?: string;
  
  // New fields for enhanced UI
  access_group?: 'individual' | 'team' | 'organization';
  tags?: string[];
  dataset_id?: string;
  can_edit?: boolean;
  can_delete?: boolean;
  
  // Content metadata
  page_count?: number;
  word_count?: number;
  character_count?: number;
  language?: string;
}

export interface RAGDataset {
  id: string;
  user_id: string;
  dataset_name: string;
  description?: string;
  chunking_strategy: string;
  chunk_size: number;
  chunk_overlap: number;
  embedding_model: string;
  document_count: number;
  chunk_count: number;
  vector_count: number;
  total_size_bytes: number;
  created_at: string;
  updated_at: string;
}

export interface CreateDatasetRequest {
  dataset_name: string;
  description?: string;
  chunking_strategy?: 'hybrid' | 'semantic' | 'fixed';
  chunk_size?: number;
  chunk_overlap?: number;
  embedding_model?: string;
}

export interface SearchResult {
  document: string;
  metadata: any;
  similarity: number;
  chunk_id: string;
  source_document_id: string;
}

export interface SearchResponse {
  query: string;
  results: SearchResult[];
}

export interface DocumentContext {
  document_id: string;
  document_name: string;
  query: string;
  relevant_chunks: SearchResult[];
  context_text: string;
}

export interface RAGStatistics {
  user_id: string;
  document_count: number;
  dataset_count: number;
  total_size_bytes: number;
  total_size_mb: number;
  total_chunks: number;
  processed_documents: number;
  pending_documents: number;
  failed_documents: number;
}

export interface ConversationHistoryResult {
  conversation_id: string;
  message_id: string;
  content: string;
  role: string;
  created_at: string;
  conversation_title: string;
  agent_name: string;
  relevance_score: number;
}

/**
 * List user's documents with optional filtering
 */
export async function listDocuments(params?: {
  status?: 'pending' | 'processing' | 'completed' | 'failed';
  dataset_id?: string;
  offset?: number;
  limit?: number;
}) {
  const searchParams = new URLSearchParams();
  if (params?.status) searchParams.set('status', params.status);
  if (params?.dataset_id) searchParams.set('dataset_id', params.dataset_id);
  if (params?.offset) searchParams.set('offset', params.offset.toString());
  if (params?.limit) searchParams.set('limit', params.limit.toString());

  const query = searchParams.toString();
  return api.get<Document[]>(`/api/v1/documents${query ? `?${query}` : ''}`);
}

/**
 * Get documents for a specific dataset
 */
export async function getDocumentsByDataset(datasetId: string) {
  return api.get<Document[]>(`/api/v1/documents?dataset_id=${datasetId}`);
}

// Upload progress tracking interfaces
export interface UploadProgressEvent {
  document_id: string;
  filename: string;
  bytes_uploaded: number;
  total_bytes: number;
  percentage: number;
  status: DocumentStatus;
  error?: string;
}

export interface ProcessingProgressEvent {
  document_id: string;
  status: DocumentStatus;
  stage: 'extracting' | 'chunking' | 'embedding' | 'indexing' | 'completed';
  progress_percentage: number;
  chunks_processed: number;
  total_chunks: number;
  error?: string;
}

export interface BulkUploadOptions {
  dataset_id?: string;
  chunking_strategy?: 'hybrid'; // Always hybrid for AI-driven optimization
  embedding_model?: string;
  access_group?: 'individual' | 'team' | 'organization';
  team_members?: string[];
  tags?: string[];
  auto_process?: boolean;
}

/**
 * Upload document with progress tracking
 */
export async function uploadDocument(
  file: File, 
  options: BulkUploadOptions = {},
  onProgress?: (event: UploadProgressEvent) => void
) {
  const formData = new FormData();
  formData.append('file', file);
  
  // Add options to form data
  Object.entries(options).forEach(([key, value]) => {
    if (value !== undefined) {
      if (Array.isArray(value)) {
        formData.append(key, JSON.stringify(value));
      } else {
        formData.append(key, value.toString());
      }
    }
  });

  const uploadId = crypto.randomUUID();
  const tenantInfo = getTenantInfo();

  if (!tenantInfo) {
    throw new Error('Tenant information not available. Please log in again.');
  }

  return api.upload<Document>('/api/v1/documents', formData, {
    headers: {
      'X-Upload-ID': uploadId,
      'X-Tenant-Domain': tenantInfo.domain,
    },
    onUploadProgress: (progressEvent) => {
      if (onProgress && progressEvent.total) {
        const percentage = Math.round((progressEvent.loaded / progressEvent.total) * 100);
        onProgress({
          document_id: uploadId,
          filename: file.name,
          bytes_uploaded: progressEvent.loaded,
          total_bytes: progressEvent.total,
          percentage,
          status: percentage < 100 ? 'uploading' : 'processing'
        });
      }
    }
  });
}

/**
 * Get specific document
 */
export async function getDocument(documentId: string) {
  // Documents are now proxied through the documents API which wraps files
  return api.get<Document>(`/api/v1/documents/${documentId}`);
}

/**
 * Process document (chunking and embedding generation)
 */
export async function processDocument(
  documentId: string, 
  chunkingStrategy?: 'hybrid' | 'semantic' | 'fixed'
) {
  const params = new URLSearchParams();
  if (chunkingStrategy) {
    params.set('chunking_strategy', chunkingStrategy);
  }

  return api.post<{
    status: string;
    document_id: string;
    chunk_count: number;
    vector_store_ids: string[];
  }>(`/api/v1/documents/${documentId}/process${params.toString() ? `?${params.toString()}` : ''}`);
}

/**
 * Delete document
 */
export async function deleteDocument(documentId: string) {
  return api.delete(`/api/v1/documents/${documentId}`);
}

/**
 * Get document context for query
 */
export async function getDocumentContext(
  documentId: string, 
  query: string, 
  contextSize: number = 3
) {
  const params = new URLSearchParams({
    query,
    context_size: contextSize.toString(),
  });

  return api.get<DocumentContext>(`/api/v1/documents/${documentId}/context?${params.toString()}`);
}

/**
 * Create RAG dataset
 */
export async function createDataset(request: CreateDatasetRequest) {
  return api.post<RAGDataset>('/api/v1/datasets', request);
}

/**
 * List user's RAG datasets
 */
export async function listDatasets() {
  return api.get<RAGDataset[]>('/api/v1/datasets');
}

/**
 * Delete RAG dataset
 */
export async function deleteDataset(datasetId: string) {
  return api.delete(`/api/v1/datasets/${datasetId}`);
}

/**
 * Search documents using RAG
 */
export async function searchDocuments(params: {
  query: string;
  dataset_ids?: string[];
  top_k?: number;
  similarity_threshold?: number;
  search_method?: 'vector' | 'hybrid' | 'keyword';
}) {
  const searchParams = new URLSearchParams({
    query: params.query,
  });
  
  if (params.dataset_ids && params.dataset_ids.length > 0) {
    params.dataset_ids.forEach(id => searchParams.append('dataset_ids', id));
  }
  if (params.top_k) searchParams.set('top_k', params.top_k.toString());
  if (params.similarity_threshold) searchParams.set('similarity_threshold', params.similarity_threshold.toString());
  if (params.search_method) searchParams.set('search_method', params.search_method);

  return api.post<SearchResponse>(`/api/v1/search?${searchParams.toString()}`);
}

/**
 * Get RAG usage statistics
 */
export async function getRAGStatistics() {
  return api.get<RAGStatistics>('/api/v1/statistics');
}

/**
 * Upload multiple files with batch progress tracking
 */
export async function uploadMultipleDocuments(
  files: File[], 
  options: BulkUploadOptions = {},
  onProgress?: (events: UploadProgressEvent[]) => void
) {
  const fileArray = Array.from(files);
  const progressEvents: UploadProgressEvent[] = [];
  
  const uploadPromises = fileArray.map(file => 
    uploadDocument(file, options, (event) => {
      const existingIndex = progressEvents.findIndex(e => e.document_id === event.document_id);
      if (existingIndex >= 0) {
        progressEvents[existingIndex] = event;
      } else {
        progressEvents.push(event);
      }
      onProgress?.(progressEvents);
    })
  );
  
  return Promise.allSettled(uploadPromises);
}

/**
 * Validate files before upload
 */
export function validateFiles(files: FileList | File[]): {
  valid: File[];
  invalid: { file: File; reason: string; }[];
} {
  const fileArray = Array.from(files);
  const valid: File[] = [];
  const invalid: { file: File; reason: string; }[] = [];

  const supportedTypes = ['pdf', 'docx', 'txt', 'md', 'csv', 'xlsx', 'pptx', 'html', 'json'];
  const maxFileSize = 50 * 1024 * 1024; // 50MB

  for (const file of fileArray) {
    const extension = file.name.split('.').pop()?.toLowerCase();
    
    if (!extension || !supportedTypes.includes(extension)) {
      invalid.push({ file, reason: `Unsupported file type: ${extension}` });
      continue;
    }

    if (file.size > maxFileSize) {
      invalid.push({ file, reason: `File too large: ${Math.round(file.size / 1024 / 1024)}MB (max: 50MB)` });
      continue;
    }

    if (file.size === 0) {
      invalid.push({ file, reason: 'Empty file' });
      continue;
    }

    valid.push(file);
  }

  return { valid, invalid };
}

/**
 * Get processing status for multiple documents
 */
export async function getProcessingStatus(documentIds: string[]) {
  return api.post<{
    [documentId: string]: {
      status: DocumentStatus;
      progress: number;
      stage?: string;
      error?: string;
    };
  }>('/api/v1/documents/processing-status', { document_ids: documentIds });
}

/**
 * Subscribe to real-time processing updates via WebSocket
 */
export function subscribeToProcessingUpdates(
  documentIds: string[],
  onUpdate: (event: ProcessingProgressEvent) => void,
  onError?: (error: Error) => void
): () => void {
  // Get auth token for WebSocket connection
  const token = localStorage.getItem('auth_token');
  if (!token) {
    onError?.(new Error('No authentication token available'));
    return () => {};
  }

  // WebSocket URL - use relative ws:// for browser, proxy handles routing
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/ws/documents/processing`;
  const ws = new WebSocket(`${wsUrl}?token=${token}&document_ids=${documentIds.join(',')}`);

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data) as ProcessingProgressEvent;
      onUpdate(data);
    } catch (error) {
      onError?.(new Error('Invalid WebSocket message format'));
    }
  };

  ws.onerror = (error) => {
    onError?.(new Error('WebSocket connection error'));
  };

  ws.onclose = (event) => {
    if (event.code !== 1000) { // Not a normal close
      onError?.(new Error(`WebSocket closed unexpectedly: ${event.reason}`));
    }
  };

  // Return cleanup function
  return () => {
    if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
      ws.close(1000, 'Client disconnect');
    }
  };
}

/**
 * Reprocess document with new settings
 */
export async function reprocessDocument(
  documentId: string,
  options: {
    chunking_strategy?: 'hybrid'; // Always hybrid for AI-driven optimization
    embedding_model?: string;
  },
  onProgress?: (event: ProcessingProgressEvent) => void
) {
  return api.post<Document>(`/api/v1/documents/${documentId}/reprocess`, options);
}

/**
 * Generate summary for a document
 */
export async function generateSummary(documentId: string) {
  return api.get<{
    summary: string;
    key_topics?: string[];
    document_type?: string;
    language?: string;
    metadata?: Record<string, any>;
  }>(`/api/v1/documents/${documentId}/summary`);
}

/**
 * Search conversation history
 */
export async function searchConversationHistory(params: {
  query: string;
  agent_filter?: string[];
  days_back?: number;
  limit?: number;
}) {
  const searchParams = new URLSearchParams({
    query: params.query,
  });

  if (params.agent_filter && params.agent_filter.length > 0) {
    params.agent_filter.forEach(id => searchParams.append('agent_filter', id));
  }
  if (params.days_back) searchParams.set('days_back', params.days_back.toString());
  if (params.limit) searchParams.set('limit', params.limit.toString());

  return api.get<ConversationHistoryResult[]>(`/api/v1/history/search?${searchParams.toString()}`);
}

// Create singleton for direct imports
export const documentService = {
  listDocuments,
  getDocument,
  uploadDocument,
  processDocument,
  deleteDocument,
  getDocumentContext,
  createDataset,
  listDatasets,
  deleteDataset,
  searchDocuments,
  getRAGStatistics,
  uploadMultipleDocuments,
  validateFiles,
  getProcessingStatus,
  subscribeToProcessingUpdates,
  reprocessDocument,
  generateSummary,
  searchConversationHistory,
  getDocumentsByDataset
};