'use client';

import React, { useState, useEffect } from 'react';
import { useSearchParams } from 'next/navigation';
import { Plus, Search, Filter, Database, FileText, BarChart3,
       Trash2, Edit3, Eye, Lock, Users, Globe, Upload } from 'lucide-react';
import {
  Dataset,
  Document,
  AccessGroup,
  AccessFilter,
} from '@/services';
import { AppLayout } from '@/components/layout/app-layout';
import { AuthGuard } from '@/components/auth/auth-guard';
import { GT2_CAPABILITIES } from '@/lib/capabilities';
import {
  DatasetCard,
  DatasetCreateModal,
  DatasetEditModal,
  BulkUpload,
  DocumentSummaryModal,
  CreateDatasetData,
  UpdateDatasetData,
  DatasetDetailsDrawer
} from '@/components/datasets';
import { DatasetDocumentsModal } from '@/components/datasets/dataset-documents-modal';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { usePageTitle } from '@/hooks/use-page-title';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { useDatasets, useDatasetSummary, useCreateDataset, useUpdateDataset, useDeleteDataset, datasetKeys } from '@/hooks/use-datasets';
import { useQueryClient } from '@tanstack/react-query';
import { formatStorageSize } from '@/lib/utils';

// Statistics interface
interface DatasetSummary {
  total_datasets: number;
  owned_datasets: number;
  team_datasets: number;
  org_datasets: number;
  total_documents: number;
  assigned_documents: number;
  unassigned_documents: number;
  total_storage_mb: number;
  assigned_storage_mb: number;
  unassigned_storage_mb: number;
  is_admin?: boolean;
  total_tenant_storage_mb?: number;
}



function DatasetsPageContent() {
  usePageTitle('Datasets');
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();

  // Filter and search state
  const [searchQuery, setSearchQuery] = useState('');
  const [accessFilter, setAccessFilter] = useState<AccessFilter>('all');

  // React Query hooks
  const { data: datasets = [], isLoading: loading } = useDatasets(accessFilter);
  const { data: summary = null } = useDatasetSummary();
  const createDataset = useCreateDataset();
  const updateDataset = useUpdateDataset();
  const deleteDataset = useDeleteDataset();

  // Helper to refresh dataset data
  const refreshDatasets = () => {
    queryClient.invalidateQueries({ queryKey: datasetKeys.all });
  };

  // UI state
  const [selectedDatasetId, setSelectedDatasetId] = useState<string | null>(null);
  const [showDetailsDrawer, setShowDetailsDrawer] = useState(false);
  const [selectedDatasets, setSelectedDatasets] = useState<string[]>([]);

  // Modal states
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [showBulkUpload, setShowBulkUpload] = useState(false);
  const [selectedDatasetForUpload, setSelectedDatasetForUpload] = useState<string>('');
  const [editingDataset, setEditingDataset] = useState<Dataset | null>(null);
  const [showDocumentSummary, setShowDocumentSummary] = useState(false);
  const [summaryDocumentId, setSummaryDocumentId] = useState<string>('');
  const [showDocumentsModal, setShowDocumentsModal] = useState(false);
  const [documentsDatasetId, setDocumentsDatasetId] = useState<string | null>(null);
  const [documentsDatasetName, setDocumentsDatasetName] = useState<string>('');
  const [lastUploadedDatasetId, setLastUploadedDatasetId] = useState<string | null>(null);
  const [initialDocuments, setInitialDocuments] = useState<any[]>([]); // Documents from recent upload

  // Clear any stale dataset selections on mount to prevent foreign key errors
  useEffect(() => {
    setSelectedDatasetForUpload('');
    setSelectedDatasets([]);
  }, []);

  // Dataset action handlers
  const handleCreateDataset = async (datasetData: CreateDatasetData) => {
    try {
      const result = await createDataset.mutateAsync({
        name: datasetData.name,
        description: datasetData.description,
        access_group: datasetData.access_group,
        team_members: datasetData.team_members,
        tags: datasetData.tags
      });
      console.log('Dataset created successfully:', result?.name);
    } catch (error) {
      console.error('Failed to create dataset:', error);
    }
  };

  const handleDatasetView = (datasetId: string) => {
    const dataset = datasets.find(d => d.id === datasetId);
    setDocumentsDatasetId(datasetId);
    setDocumentsDatasetName(dataset?.name || '');
    setShowDocumentsModal(true);
  };

  const handleDatasetEdit = (datasetId: string) => {
    const dataset = datasets.find(d => d.id === datasetId);
    if (dataset) {
      setEditingDataset(dataset);
      setShowEditModal(true);
    }
  };

  const handleUpdateDataset = async (datasetId: string, updateData: UpdateDatasetData) => {
    try {
      const result = await updateDataset.mutateAsync({ datasetId, updateData });
      console.log('Dataset updated successfully:', result?.name);
      setShowEditModal(false);
      setEditingDataset(null);
    } catch (error) {
      console.error('Failed to update dataset:', error);
    }
  };

  const handleDatasetDelete = async (datasetId: string) => {
    if (!confirm('Are you sure you want to delete this dataset? This action cannot be undone.')) {
      return;
    }

    try {
      await deleteDataset.mutateAsync(datasetId);
      console.log('Dataset deleted successfully');
    } catch (error) {
      console.error('Failed to delete dataset:', error);
    }
  };

  const handleDatasetUpload = (datasetId: string) => {
    console.log('Uploading to dataset:', datasetId);

    // Verify the dataset still exists in our current list
    const dataset = datasets.find(d => d.id === datasetId);
    if (!dataset) {
      console.error('Dataset not found:', datasetId);
      alert('Dataset not found. Please refresh the page and try again.');
      refreshDatasets(); // Refresh datasets
      return;
    }

    // Store the dataset ID for routing after upload completes
    setLastUploadedDatasetId(datasetId);
    setSelectedDatasetForUpload(datasetId);
    setShowBulkUpload(true);
  };

  const handleDatasetProcess = (datasetId: string) => {
    console.log('Processing dataset:', datasetId);
    // TODO: Trigger processing for all documents in dataset
  };

  const handleDatasetReindex = (datasetId: string) => {
    console.log('Reindexing dataset:', datasetId);
    // TODO: Trigger reindexing
  };


  // Filter datasets based on search query
  const filteredDatasets = datasets.filter(dataset =>
    dataset.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    dataset.description?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    dataset.tags.some(tag => tag.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  // Get icon for access group
  const getAccessIcon = (accessGroup: AccessGroup) => {
    switch (accessGroup) {
      case 'individual': return <Lock className="w-4 h-4" />;
      case 'team': return <Users className="w-4 h-4" />;
      case 'organization': return <Globe className="w-4 h-4" />;
      default: return <Lock className="w-4 h-4" />;
    }
  };

  // Get access group color
  const getAccessColor = (accessGroup: AccessGroup) => {
    switch (accessGroup) {
      case 'individual': return 'text-gt-gray-600';
      case 'team': return 'text-blue-600';
      case 'organization': return 'text-green-600';
      default: return 'text-gt-gray-600';
    }
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="bg-gt-white rounded-lg shadow-sm border p-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gt-gray-900 flex items-center gap-3">
              <Database className="w-8 h-8 text-gt-green" />
              Dataset Management Hub
            </h1>
            <p className="text-gt-gray-600 mt-1">
              Manage your datasets and documents for RAG in one unified interface
            </p>
          </div>
        </div>
      </div>

      {/* Statistics Cards */}
      {summary && (
        <div className={`grid grid-cols-1 gap-4 ${summary.is_admin ? 'md:grid-cols-3' : 'md:grid-cols-2'}`}>
          <button
            onClick={() => setAccessFilter('mine')}
            className="w-full bg-gradient-to-br from-green-50 to-green-100 p-4 rounded-lg hover:shadow-md transition-all cursor-pointer"
          >
            <div className="flex items-center justify-between">
              <div>
                <p className="text-green-600 text-sm font-medium">My Datasets</p>
                <p className="text-2xl font-bold text-green-900">{summary.owned_datasets}</p>
              </div>
              <Lock className="w-8 h-8 text-green-600" />
            </div>
          </button>

          <div className="bg-gradient-to-br from-orange-50 to-orange-100 p-4 rounded-lg">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-orange-600 text-sm font-medium">My Storage</p>
                <p className="text-2xl font-bold text-orange-900">
                  {formatStorageSize(summary.total_storage_mb)}
                </p>
                {/* TODO: Show % of allocation when storage_allocation_mb added to tenant schema */}
              </div>
              <BarChart3 className="w-8 h-8 text-orange-600" />
            </div>
          </div>

          {summary.is_admin && summary.total_tenant_storage_mb !== undefined && (
            <div className="bg-gradient-to-br from-blue-50 to-blue-100 p-4 rounded-lg">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-blue-600 text-sm font-medium">Total Tenant Storage</p>
                  <p className="text-2xl font-bold text-blue-900">
                    {formatStorageSize(summary.total_tenant_storage_mb)}
                  </p>
                </div>
                <BarChart3 className="w-8 h-8 text-blue-600" />
              </div>
            </div>
          )}
        </div>
      )}

      {/* Main Content Area */}
      <div className="bg-gt-white rounded-lg shadow-sm border p-6">
        <div className="space-y-6">
          {/* Controls */}
          <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-center justify-between">
                <div className="flex flex-col sm:flex-row gap-4 flex-1">
                  {/* Search */}
                  <div className="relative flex-1 max-w-md">
                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gt-gray-400 w-4 h-4 z-10" />
                    <Input
                      type="text"
                      placeholder="Search datasets..."
                      value={searchQuery}
                      onChange={(value) => setSearchQuery(value)}
                      className="pl-10"
                      clearable
                    />
                  </div>

                  {/* Access Filter */}
                  <div className="flex items-center gap-2">
                    <Filter className="w-4 h-4 text-gt-gray-400" />
                    <Select value={accessFilter} onValueChange={(value: AccessFilter) => setAccessFilter(value)}>
                      <SelectTrigger className="w-40">
                        <SelectValue placeholder="Filter by access" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">All Access</SelectItem>
                        <SelectItem value="mine">My Datasets</SelectItem>
                        <SelectItem value="org">Organization</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setShowBulkUpload(true)}
                    className="flex items-center gap-2"
                  >
                    <Upload className="w-4 h-4" />
                    Upload Documents
                  </Button>
                  <Button
                    size="sm"
                    onClick={() => setShowCreateModal(true)}
                    className="flex items-center gap-2"
                  >
                    <Plus className="w-4 h-4" />
                    New Dataset
                  </Button>
                </div>
              </div>

          {/* Dataset List */}
          {loading ? (
                <div className="flex items-center justify-center py-12">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gt-green"></div>
                </div>
              ) : (
                <div className="space-y-3">
                  {filteredDatasets.map((dataset) => (
                    <DatasetCard
                      key={dataset.id}
                      dataset={{
                        ...dataset,
                        embedding_model: 'BAAI/bge-m3', // TODO: Get from dataset
                        search_method: 'hybrid', // TODO: Get from dataset
                        processing_status: 'idle' // TODO: Get actual status
                      }}
                      onView={handleDatasetView}
                      onEdit={handleDatasetEdit}
                      onDelete={handleDatasetDelete}
                      onUpload={handleDatasetUpload}
                      onProcess={handleDatasetProcess}
                      onReindex={handleDatasetReindex}
                    />
                  ))}
                </div>
              )}

          {!loading && filteredDatasets.length === 0 && (
                <div className="text-center py-12">
                  <Database className="w-12 h-12 text-gt-gray-400 mx-auto mb-4" />
                  <h3 className="text-lg font-medium text-gt-gray-900 mb-2">No datasets found</h3>
                  <p className="text-gt-gray-600 mb-6">
                    {searchQuery 
                      ? `No datasets match "${searchQuery}"`
                      : "Create your first dataset to get started"
                    }
                  </p>
                  <Button onClick={() => setShowCreateModal(true)}>
                    Create Dataset
                  </Button>
                </div>
              )}
        </div>
      </div>

      {/* Modals */}
      <DatasetCreateModal
        open={showCreateModal}
        onOpenChange={setShowCreateModal}
        onCreateDataset={handleCreateDataset}
        loading={createDataset.isPending}
      />

      <BulkUpload
        open={showBulkUpload}
        onOpenChange={(open) => {
          setShowBulkUpload(open);
          if (!open) {
            setSelectedDatasetForUpload(''); // Clear selection when modal closes
          }
        }}
        datasets={datasets.map(d => ({
          id: d.id,
          name: d.name,
          document_count: d.document_count
        }))}
        preselectedDatasetId={selectedDatasetForUpload}
        onCreateDataset={() => {
          setShowBulkUpload(false);
          setShowCreateModal(true);
        }}
        onUploadStart={(datasetId, documents) => {
          // Route to documents page immediately when upload starts
          // Store any initial documents to display immediately
          if (documents && documents.length > 0) {
            setInitialDocuments(documents);
          }
          handleDatasetView(datasetId);
        }}
        onUploadComplete={async (results) => {
          console.log('Upload documents completed:', results);
          // React Query will auto-refresh via cache invalidation
        }}
      />

      <DatasetEditModal
        open={showEditModal}
        onOpenChange={(open) => {
          setShowEditModal(open);
          if (!open) {
            setEditingDataset(null);
          }
        }}
        onUpdateDataset={handleUpdateDataset}
        dataset={editingDataset}
        loading={updateDataset.isPending}
      />

      <DatasetDetailsDrawer
        datasetId={selectedDatasetId}
        isOpen={showDetailsDrawer}
        onClose={() => {
          setShowDetailsDrawer(false);
          setSelectedDatasetId(null);
        }}
        onDatasetDeleted={refreshDatasets}
        onDatasetUpdated={refreshDatasets}
      />

      <DocumentSummaryModal
        open={showDocumentSummary}
        onOpenChange={(open) => {
          setShowDocumentSummary(open);
          if (!open) {
            setSummaryDocumentId('');
          }
        }}
        documentId={summaryDocumentId}
      />

      <DatasetDocumentsModal
        open={showDocumentsModal}
        onOpenChange={(open) => {
          setShowDocumentsModal(open);
          if (!open) {
            setDocumentsDatasetId(null);
            setDocumentsDatasetName('');
            setInitialDocuments([]); // Clear initial documents when modal closes
          }
        }}
        datasetId={documentsDatasetId}
        datasetName={documentsDatasetName}
        initialDocuments={initialDocuments}
      />
    </div>
  );
}

export default function DatasetsPage() {
  return (
    <AuthGuard requiredCapabilities={[GT2_CAPABILITIES.DATASETS_READ]}>
      <AppLayout>
        <DatasetsPageContent />
      </AppLayout>
    </AuthGuard>
  );
}