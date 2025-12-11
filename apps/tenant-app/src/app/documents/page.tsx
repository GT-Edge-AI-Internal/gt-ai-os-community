'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { useDropzone } from 'react-dropzone';
import { Header } from '@/components/layout/header';
import { Sidebar } from '@/components/layout/sidebar';
import { Button } from '@/components/ui/button';
import { LoadingScreen } from '@/components/ui/loading-screen';
import { useAuthStore } from '@/stores/auth-store';
import { AuthGuard } from '@/components/auth/auth-guard';
import { GT2_CAPABILITIES } from '@/lib/capabilities';
import { listDocuments, listDatasets, uploadDocument, processDocument } from '@/services/documents';
import {
  Upload,
  File,
  FileText,
  FileImage,
  FileCode,
  FileArchive,
  Search,
  Filter,
  Download,
  Trash2,
  Eye,
  MoreVertical,
  AlertCircle,
  CheckCircle,
  Clock,
  Brain,
  Database,
  Layers,
  RefreshCw,
  Plus,
  FolderOpen,
  Tags,
  Calendar,
  User,
  FileCheck,
  Activity,
  Zap,
} from 'lucide-react';
import { formatDateTime } from '@/lib/utils';

interface Document {
  id: string;
  filename: string;
  original_name: string;
  file_type: string;
  file_size: number;
  processing_status: 'pending' | 'processing' | 'completed' | 'failed';
  chunk_count?: number;
  vector_count?: number;
  dataset_id?: string;
  dataset_name?: string;
  uploaded_at: string;
  processed_at?: string;
  error_message?: string;
  metadata: {
    pages?: number;
    language?: string;
    author?: string;
    created_date?: string;
  };
  processing_progress?: number;
}

interface RAGDataset {
  id: string;
  name: string;
  description: string;
  document_count: number;
  chunk_count: number;
  vector_count: number;
  embedding_model: string;
  created_at: string;
  updated_at: string;
  status: 'active' | 'processing' | 'inactive';
  storage_size_mb: number;
}

function DocumentsPageContent() {
  const { user, isAuthenticated, isLoading } = useAuthStore();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [datasets, setDatasets] = useState<RAGDataset[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [selectedDataset, setSelectedDataset] = useState<string>('');
  const [showCreateDataset, setShowCreateDataset] = useState(false);
  const [selectedDocuments, setSelectedDocuments] = useState<Set<string>>(new Set());
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Load real data from API
  useEffect(() => {
    if (isAuthenticated) {
      loadDocumentsAndDatasets();
    }
  }, [isAuthenticated]);

  const loadDocumentsAndDatasets = async () => {
    try {
      setLoading(true);
      
      // Load documents and datasets in parallel
      const [documentsResponse, datasetsResponse] = await Promise.all([
        listDocuments(),
        listDatasets()
      ]);

      if (documentsResponse.data) {
        const docsWithMetadata = documentsResponse.data.map(doc => ({
          id: doc.id,
          filename: doc.filename,
          original_name: doc.original_filename,
          file_type: doc.file_type,
          file_size: doc.file_size_bytes,
          processing_status: doc.processing_status,
          chunk_count: doc.chunk_count,
          vector_count: doc.vector_count,
          dataset_id: undefined, // Documents aren't necessarily in datasets
          dataset_name: 'Individual Document',
          uploaded_at: doc.created_at,
          processed_at: doc.processed_at,
          error_message: doc.error_details?.message,
          metadata: {
            // Add metadata extraction if available
          },
          processing_progress: doc.processing_status === 'processing' ? 50 : undefined
        }));
        setDocuments(docsWithMetadata);
      }

      if (datasetsResponse.data) {
        const datasetsWithMetadata = datasetsResponse.data.map(ds => ({
          id: ds.id,
          name: ds.dataset_name,
          description: ds.description || '',
          document_count: ds.document_count,
          chunk_count: ds.chunk_count,
          vector_count: ds.vector_count,
          embedding_model: ds.embedding_model,
          created_at: ds.created_at,
          updated_at: ds.updated_at,
          status: 'active' as const,
          storage_size_mb: Math.round(ds.total_size_bytes / (1024 * 1024) * 100) / 100
        }));
        setDatasets(datasetsWithMetadata);
      }
    } catch (error) {
      console.error('Failed to load documents and datasets:', error);
      // Fallback to empty arrays - user can still upload
      setDocuments([]);
      setDatasets([]);
    } finally {
      setLoading(false);
    }
  };

  // Keep mock data as fallback for development if API fails
  const loadMockData = () => {
    if (isAuthenticated) {
      const mockDocuments: Document[] = [
        {
          id: '1',
          filename: 'company_handbook_2024.pdf',
          original_name: 'Company Handbook 2024.pdf',
          file_type: 'application/pdf',
          file_size: 2048576, // 2MB
          processing_status: 'completed',
          chunk_count: 45,
          vector_count: 45,
          dataset_id: 'ds_1',
          dataset_name: 'Company Policies',
          uploaded_at: '2024-01-15T10:30:00Z',
          processed_at: '2024-01-15T10:32:15Z',
          metadata: {
            pages: 67,
            language: 'en',
            author: 'HR Department',
            created_date: '2024-01-01',
          },
        },
        {
          id: '2',
          filename: 'technical_specs_v3.docx',
          original_name: 'Technical Specifications v3.docx',
          file_type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
          file_size: 1572864, // 1.5MB
          processing_status: 'processing',
          processing_progress: 67,
          dataset_id: 'ds_2',
          dataset_name: 'Technical Documentation',
          uploaded_at: '2024-01-15T11:15:00Z',
          metadata: {
            pages: 23,
            language: 'en',
          },
        },
        {
          id: '3',
          filename: 'market_research_q4.xlsx',
          original_name: 'Market Research Q4 2023.xlsx',
          file_type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
          file_size: 512000, // 500KB
          processing_status: 'failed',
          error_message: 'Unsupported file format for text extraction',
          uploaded_at: '2024-01-15T09:45:00Z',
          metadata: {},
        },
        {
          id: '4',
          filename: 'project_proposal.txt',
          original_name: 'Project Proposal - AI Initiative.txt',
          file_type: 'text/plain',
          file_size: 25600, // 25KB
          processing_status: 'completed',
          chunk_count: 8,
          vector_count: 8,
          dataset_id: 'ds_3',
          dataset_name: 'Project Documents',
          uploaded_at: '2024-01-14T16:20:00Z',
          processed_at: '2024-01-14T16:21:30Z',
          metadata: {
            language: 'en',
          },
        },
        {
          id: '5',
          filename: 'meeting_notes_jan.md',
          original_name: 'Meeting Notes - January 2024.md',
          file_type: 'text/markdown',
          file_size: 12800, // 12.5KB
          processing_status: 'pending',
          uploaded_at: '2024-01-15T14:00:00Z',
          metadata: {},
        },
      ];

      const mockDatasets: RAGDataset[] = [
        {
          id: 'ds_1',
          name: 'Company Policies',
          description: 'HR policies, handbooks, and company guidelines',
          document_count: 12,
          chunk_count: 234,
          vector_count: 234,
          embedding_model: 'BAAI/bge-m3',
          created_at: '2024-01-10T09:00:00Z',
          updated_at: '2024-01-15T10:32:15Z',
          status: 'active',
          storage_size_mb: 15.7,
        },
        {
          id: 'ds_2',
          name: 'Technical Documentation',
          description: 'API docs, technical specifications, and architecture guides',
          document_count: 8,
          chunk_count: 156,
          vector_count: 156,
          embedding_model: 'BAAI/bge-m3',
          created_at: '2024-01-12T14:30:00Z',
          updated_at: '2024-01-15T11:15:00Z',
          status: 'processing',
          storage_size_mb: 8.2,
        },
        {
          id: 'ds_3',
          name: 'Project Documents',
          description: 'Project proposals, meeting notes, and planning documents',
          document_count: 5,
          chunk_count: 67,
          vector_count: 67,
          embedding_model: 'BAAI/bge-m3',
          created_at: '2024-01-08T11:00:00Z',
          updated_at: '2024-01-14T16:21:30Z',
          status: 'active',
          storage_size_mb: 4.1,
        },
      ];

      setDocuments(mockDocuments);
      setDatasets(mockDatasets);
      setLoading(false);
    }
  };

  // Filter documents based on search and status
  const filteredDocuments = documents.filter(doc => {
    const matchesSearch = searchQuery === '' || 
      doc.original_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      doc.dataset_name?.toLowerCase().includes(searchQuery.toLowerCase());
    
    const matchesStatus = statusFilter === 'all' || doc.processing_status === statusFilter;
    const matchesDataset = selectedDataset === '' || doc.dataset_id === selectedDataset;
    
    return matchesSearch && matchesStatus && matchesDataset;
  });

  // File upload handling with real API
  const handleFileUpload = useCallback(async (files: FileList | File[]) => {
    setUploading(true);
    
    // Convert FileList to Array
    const fileArray = Array.from(files);
    
    try {
      // Upload files one by one
      for (const file of fileArray) {
        console.log('Uploading file:', file.name);
        
        // Upload document
        const uploadResponse = await uploadDocument(file, {
          dataset_id: selectedDataset || undefined
        });
        
        if (uploadResponse.data) {
          const uploadedDoc = uploadResponse.data;
          
          // Add to documents list immediately
          const newDocument = {
            id: uploadedDoc.id,
            filename: uploadedDoc.filename,
            original_name: uploadedDoc.original_filename,
            file_type: uploadedDoc.file_type,
            file_size: uploadedDoc.file_size_bytes,
            processing_status: uploadedDoc.processing_status,
            chunk_count: uploadedDoc.chunk_count,
            vector_count: uploadedDoc.vector_count,
            dataset_id: undefined,
            dataset_name: 'Individual Document',
            uploaded_at: uploadedDoc.created_at,
            processed_at: uploadedDoc.processed_at,
            metadata: {}
          };
          
          setDocuments(prev => [newDocument, ...prev]);
          
          // Auto-process the document
          if (uploadedDoc.processing_status === 'pending') {
            try {
              await processDocument(uploadedDoc.id, 'hybrid');
              console.log(`Started processing document: ${file.name}`);
              
              // Update document status
              setDocuments(prev => prev.map(doc => 
                doc.id === uploadedDoc.id 
                  ? { ...doc, processing_status: 'processing' }
                  : doc
              ));
            } catch (processError) {
              console.error(`Failed to process document ${file.name}:`, processError);
            }
          }
        } else if (uploadResponse.error) {
          console.error(`Upload failed for ${file.name}:`, uploadResponse.error);
          // You could show a toast notification here
        }
      }
      
      // Reload documents and datasets to get updated stats
      await loadDocumentsAndDatasets();
      
    } catch (error) {
      console.error('File upload error:', error);
    } finally {
      setUploading(false);
    }
  }, [selectedDataset]);

  // Legacy simulation code kept as fallback
  const simulateFileUpload = (files: FileList | File[]) => {
    setUploading(true);
    
    const fileArray = Array.from(files);
    
    fileArray.forEach((file) => {
      
      // Create a new document entry
      const newDocument: Document = {
        id: `upload_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
        filename: file.name.replace(/[^a-zA-Z0-9.-]/g, '_'),
        original_name: file.name,
        file_type: file.type,
        file_size: file.size,
        processing_status: 'pending',
        uploaded_at: new Date().toISOString(),
        metadata: {},
      };
      
      setDocuments(prev => [newDocument, ...prev]);
      
      // Simulate processing delay
      setTimeout(() => {
        setDocuments(prev => prev.map(doc => 
          doc.id === newDocument.id 
            ? { ...doc, processing_status: 'processing', processing_progress: 0 }
            : doc
        ));
        
        // Simulate progress updates
        const progressInterval = setInterval(() => {
          setDocuments(prev => prev.map(doc => {
            if (doc.id === newDocument.id && doc.processing_progress !== undefined) {
              const newProgress = Math.min((doc.processing_progress || 0) + 15, 100);
              if (newProgress >= 100) {
                clearInterval(progressInterval);
                return {
                  ...doc,
                  processing_status: 'completed',
                  processing_progress: undefined,
                  chunk_count: Math.floor(Math.random() * 20) + 5,
                  vector_count: Math.floor(Math.random() * 20) + 5,
                  processed_at: new Date().toISOString(),
                  dataset_id: datasets[0]?.id,
                  dataset_name: datasets[0]?.name,
                };
              }
              return { ...doc, processing_progress: newProgress };
            }
            return doc;
          }));
        }, 800);
      }, 1000);
    });
    
    setTimeout(() => setUploading(false), 1500);
  };

  // File input change handler
  const handleFileInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (files && files.length > 0) {
      handleFileUpload(files);
    }
  };

  // Drag and drop handlers
  const handleDragEnter = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    
    const files = e.dataTransfer.files;
    if (files && files.length > 0) {
      handleFileUpload(files);
    }
  };

  // Click handler for upload area
  const handleUploadClick = () => {
    fileInputRef.current?.click();
  };

  const getFileIcon = (fileType: string) => {
    if (fileType.includes('pdf')) return <FileText className="h-5 w-5 text-red-600" />;
    if (fileType.includes('image')) return <FileImage className="h-5 w-5 text-green-600" />;
    if (fileType.includes('text') || fileType.includes('markdown')) return <FileText className="h-5 w-5 text-blue-600" />;
    if (fileType.includes('code') || fileType.includes('json')) return <FileCode className="h-5 w-5 text-purple-600" />;
    if (fileType.includes('zip') || fileType.includes('archive')) return <FileArchive className="h-5 w-5 text-orange-600" />;
    return <File className="h-5 w-5 text-gray-600" />;
  };

  const getStatusBadge = (status: string, progress?: number) => {
    switch (status) {
      case 'completed':
        return (
          <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800">
            <CheckCircle className="h-3 w-3 mr-1" />
            Processed
          </span>
        );
      case 'processing':
        return (
          <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
            <RefreshCw className="h-3 w-3 mr-1 animate-spin" />
            Processing {progress ? `${progress}%` : ''}
          </span>
        );
      case 'pending':
        return (
          <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
            <Clock className="h-3 w-3 mr-1" />
            Pending
          </span>
        );
      case 'failed':
        return (
          <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-red-100 text-red-800">
            <AlertCircle className="h-3 w-3 mr-1" />
            Failed
          </span>
        );
      default:
        return null;
    }
  };

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };


  if (isLoading) {
    return <LoadingScreen />;
  }

  if (!isAuthenticated) {
    return <div>Please log in to access documents.</div>;
  }

  return (
    <div className="h-screen flex bg-gt-gray-50">
      {/* Sidebar */}
      <Sidebar 
        open={sidebarOpen} 
        onClose={() => setSidebarOpen(false)}
        user={{ id: 1, email: "user@example.com" }}
        onMenuClick={() => {}}
      />

      {/* Main Content */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <Header 
          user={user}
          onMenuClick={() => setSidebarOpen(true)}
        />

        {/* Documents Interface */}
        <main className="flex-1 bg-gt-white overflow-hidden">
          <div className="h-full flex flex-col p-6">
            {/* Page Header */}
            <div className="flex justify-between items-center mb-6">
              <div>
                <h1 className="text-2xl font-bold text-gt-gray-900">Document Management</h1>
                <p className="text-gt-gray-600 mt-1">
                  Upload, process, and manage your documents for AI-powered search and analysis
                </p>
              </div>
              <div className="flex space-x-3">
                <Button
                  variant="secondary"
                  onClick={() => setShowCreateDataset(true)}
                >
                  <Plus className="h-4 w-4 mr-2" />
                  New Dataset
                </Button>
                <Button onClick={handleUploadClick}>
                  <Upload className="h-4 w-4 mr-2" />
                  Upload Files
                  <input
                    ref={fileInputRef}
                    type="file"
                    multiple
                    accept=".pdf,.doc,.docx,.txt,.md,.csv,.json"
                    onChange={handleFileInputChange}
                    className="hidden"
                  />
                </Button>
              </div>
            </div>

            {/* Stats Cards */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
              <div className="bg-white rounded-lg border border-gt-gray-200 p-4">
                <div className="flex items-center">
                  <div className="flex-shrink-0">
                    <FileText className="h-6 w-6 text-blue-600" />
                  </div>
                  <div className="ml-3">
                    <p className="text-sm font-medium text-gt-gray-500">Total Documents</p>
                    <p className="text-lg font-semibold text-gt-gray-900">{documents.length}</p>
                  </div>
                </div>
              </div>
              
              <div className="bg-white rounded-lg border border-gt-gray-200 p-4">
                <div className="flex items-center">
                  <div className="flex-shrink-0">
                    <Database className="h-6 w-6 text-green-600" />
                  </div>
                  <div className="ml-3">
                    <p className="text-sm font-medium text-gt-gray-500">RAG Datasets</p>
                    <p className="text-lg font-semibold text-gt-gray-900">{datasets.length}</p>
                  </div>
                </div>
              </div>
              
              <div className="bg-white rounded-lg border border-gt-gray-200 p-4">
                <div className="flex items-center">
                  <div className="flex-shrink-0">
                    <Layers className="h-6 w-6 text-purple-600" />
                  </div>
                  <div className="ml-3">
                    <p className="text-sm font-medium text-gt-gray-500">Total Chunks</p>
                    <p className="text-lg font-semibold text-gt-gray-900">
                      {documents.reduce((sum, doc) => sum + (doc.chunk_count || 0), 0)}
                    </p>
                  </div>
                </div>
              </div>
              
              <div className="bg-white rounded-lg border border-gt-gray-200 p-4">
                <div className="flex items-center">
                  <div className="flex-shrink-0">
                    <Brain className="h-6 w-6 text-orange-600" />
                  </div>
                  <div className="ml-3">
                    <p className="text-sm font-medium text-gt-gray-500">Vector Embeddings</p>
                    <p className="text-lg font-semibold text-gt-gray-900">
                      {documents.reduce((sum, doc) => sum + (doc.vector_count || 0), 0)}
                    </p>
                  </div>
                </div>
              </div>
            </div>

            {/* Upload Area */}
            <div
              onDragEnter={handleDragEnter}
              onDragLeave={handleDragLeave}
              onDragOver={handleDragOver}
              onDrop={handleDrop}
              onClick={handleUploadClick}
              className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors cursor-pointer mb-6 ${
                dragActive 
                  ? 'border-gt-green bg-gt-green/5' 
                  : 'border-gt-gray-300 hover:border-gt-green hover:bg-gt-gray-50'
              }`}
            >
              <Upload className="h-12 w-12 text-gt-gray-400 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gt-gray-900 mb-2">
                {dragActive ? 'Drop files here' : 'Upload Documents'}
              </h3>
              <p className="text-gt-gray-600 mb-4">
                Drag and drop files here, or click to select files
              </p>
              <p className="text-sm text-gt-gray-500">
                Supports PDF, DOC, DOCX, TXT, MD, CSV, and JSON files up to 10MB
              </p>
            </div>

            {/* Filters and Search */}
            <div className="flex flex-col md:flex-row gap-4 mb-6">
              <div className="flex-1">
                <div className="relative">
                  <Search className="h-5 w-5 text-gt-gray-400 absolute left-3 top-1/2 transform -translate-y-1/2" />
                  <input
                    type="text"
                    placeholder="Search documents..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery((e as React.ChangeEvent<HTMLInputElement>).target.value)}
                    className="w-full pl-10 pr-4 py-2 border border-gt-gray-300 rounded-lg focus:ring-2 focus:ring-gt-green focus:border-transparent"
                  />
                </div>
              </div>
              
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter((e as React.ChangeEvent<HTMLSelectElement>).target.value)}
                className="px-3 py-2 border border-gt-gray-300 rounded-lg focus:ring-2 focus:ring-gt-green focus:border-transparent"
              >
                <option value="all">All Status</option>
                <option value="completed">Processed</option>
                <option value="processing">Processing</option>
                <option value="pending">Pending</option>
                <option value="failed">Failed</option>
              </select>
              
              <select
                value={selectedDataset}
                onChange={(e) => setSelectedDataset((e as React.ChangeEvent<HTMLSelectElement>).target.value)}
                className="px-3 py-2 border border-gt-gray-300 rounded-lg focus:ring-2 focus:ring-gt-green focus:border-transparent"
              >
                <option value="">All Datasets</option>
                {datasets.map(dataset => (
                  <option key={dataset.id} value={dataset.id}>{dataset.name}</option>
                ))}
              </select>
            </div>

            {/* RAG Datasets Overview */}
            <div className="mb-6">
              <h2 className="text-lg font-semibold text-gt-gray-900 mb-3">RAG Datasets</h2>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {datasets.map(dataset => (
                  <div key={dataset.id} className="bg-white rounded-lg border border-gt-gray-200 p-4">
                    <div className="flex items-start justify-between mb-2">
                      <h3 className="font-medium text-gt-gray-900">{dataset.name}</h3>
                      <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${
                        dataset.status === 'active' ? 'bg-green-100 text-green-800' :
                        dataset.status === 'processing' ? 'bg-blue-100 text-blue-800' :
                        'bg-gray-100 text-gray-800'
                      }`}>
                        {dataset.status}
                      </span>
                    </div>
                    <p className="text-sm text-gt-gray-600 mb-3">{dataset.description}</p>
                    <div className="grid grid-cols-2 gap-4 text-sm">
                      <div>
                        <span className="text-gt-gray-500">Documents:</span>
                        <span className="ml-1 font-medium">{dataset.document_count}</span>
                      </div>
                      <div>
                        <span className="text-gt-gray-500">Chunks:</span>
                        <span className="ml-1 font-medium">{dataset.chunk_count}</span>
                      </div>
                      <div>
                        <span className="text-gt-gray-500">Vectors:</span>
                        <span className="ml-1 font-medium">{dataset.vector_count}</span>
                      </div>
                      <div>
                        <span className="text-gt-gray-500">Size:</span>
                        <span className="ml-1 font-medium">{dataset.storage_size_mb.toFixed(1)} MB</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Documents List */}
            <div className="flex-1 overflow-hidden">
              <div className="bg-white rounded-lg border border-gt-gray-200 h-full flex flex-col">
                <div className="px-6 py-4 border-b border-gt-gray-200">
                  <h2 className="text-lg font-semibold text-gt-gray-900">
                    Documents ({filteredDocuments.length})
                  </h2>
                </div>
                
                <div className="flex-1 overflow-y-auto">
                  {loading ? (
                    <div className="p-6 space-y-4">
                      {[...Array(5)].map((_, i) => (
                        <div key={i} className="animate-pulse">
                          <div className="flex items-center space-x-4">
                            <div className="w-10 h-10 bg-gt-gray-200 rounded"></div>
                            <div className="flex-1">
                              <div className="w-1/2 h-4 bg-gt-gray-200 rounded mb-2"></div>
                              <div className="w-1/4 h-3 bg-gt-gray-200 rounded"></div>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : filteredDocuments.length === 0 ? (
                    <div className="p-12 text-center">
                      <FolderOpen className="h-12 w-12 text-gt-gray-300 mx-auto mb-4" />
                      <h3 className="text-lg font-medium text-gt-gray-900 mb-2">No documents found</h3>
                      <p className="text-gt-gray-600">
                        Upload your first document to get started with AI-powered document search.
                      </p>
                    </div>
                  ) : (
                    <div className="divide-y divide-gt-gray-200">
                      {filteredDocuments.map(document => (
                        <div key={document.id} className="p-6 hover:bg-gt-gray-50 transition-colors">
                          <div className="flex items-start space-x-4">
                            <div className="flex-shrink-0">
                              {getFileIcon(document.file_type)}
                            </div>
                            
                            <div className="flex-1 min-w-0">
                              <div className="flex items-start justify-between">
                                <div className="flex-1">
                                  <h3 className="text-sm font-medium text-gt-gray-900 truncate">
                                    {document.original_name}
                                  </h3>
                                  <div className="mt-1 flex items-center space-x-4 text-sm text-gt-gray-500">
                                    <span>{formatFileSize(document.file_size)}</span>
                                    <span>•</span>
                                    <span>{formatDateTime(document.uploaded_at)}</span>
                                    {document.dataset_name && (
                                      <>
                                        <span>•</span>
                                        <span className="text-gt-green font-medium">{document.dataset_name}</span>
                                      </>
                                    )}
                                  </div>
                                  
                                  {document.processing_status === 'completed' && (
                                    <div className="mt-2 flex items-center space-x-4 text-sm text-gt-gray-600">
                                      <span className="flex items-center">
                                        <Layers className="h-3 w-3 mr-1" />
                                        {document.chunk_count} chunks
                                      </span>
                                      <span className="flex items-center">
                                        <Brain className="h-3 w-3 mr-1" />
                                        {document.vector_count} vectors
                                      </span>
                                      {document.metadata.pages && (
                                        <span className="flex items-center">
                                          <FileText className="h-3 w-3 mr-1" />
                                          {document.metadata.pages} pages
                                        </span>
                                      )}
                                    </div>
                                  )}
                                  
                                  {document.error_message && (
                                    <div className="mt-2 text-sm text-red-600">
                                      {document.error_message}
                                    </div>
                                  )}
                                </div>
                                
                                <div className="flex items-center space-x-3 ml-4">
                                  {getStatusBadge(document.processing_status, document.processing_progress)}
                                  
                                  <div className="flex items-center space-x-1">
                                    <Button variant="ghost" size="sm">
                                      <Eye className="h-4 w-4" />
                                    </Button>
                                    <Button variant="ghost" size="sm">
                                      <Download className="h-4 w-4" />
                                    </Button>
                                    <Button variant="ghost" size="sm">
                                      <MoreVertical className="h-4 w-4" />
                                    </Button>
                                  </div>
                                </div>
                              </div>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        </main>
      </div>

      {/* Mobile Sidebar Overlay */}
      {sidebarOpen && (
        <div 
          className="fixed inset-0 bg-black bg-opacity-50 z-40 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}
    </div>
  );
}

export default function DocumentsPage() {
  return (
    <AuthGuard requiredCapabilities={[GT2_CAPABILITIES.DOCUMENTS_READ]}>
      <DocumentsPageContent />
    </AuthGuard>
  );
}