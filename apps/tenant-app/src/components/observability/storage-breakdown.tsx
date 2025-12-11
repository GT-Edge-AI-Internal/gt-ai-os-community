'use client';

import { useEffect, useState } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell, PieChart, Pie, AreaChart, Area } from 'recharts';
import { Database, FileText, HardDrive, LayoutGrid, User, MessageSquare } from 'lucide-react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { api } from '@/services/api';
import { getUserRole } from '@/lib/permissions';
import { formatStorageSize } from '@/lib/utils';

interface DatasetStorageItem {
  id: string;
  label: string;
  document_count: number;
  storage_mb: number;
  percentage: number;
}

interface StorageOverview {
  total_documents: number;
  total_storage_mb: number;
  total_datasets: number;
  average_document_size_mb: number;
}

interface UserListItem {
  id: string;
  email: string;
  full_name: string | null;
  role: string;
}

interface FileTypeBreakdown {
  file_type: string;
  document_count: number;
  storage_mb: number;
  percentage: number;
}

interface FileInfo {
  file_name: string;
  file_size_mb: number;
  file_type: string;
  uploaded_at: string;
}

interface DatasetFileDetails {
  dataset_id: string;
  dataset_name: string;
  total_size_mb: number;
  file_count: number;
  files: FileInfo[];
}

interface UserStorageItem {
  id: string;
  label: string;
  document_count: number;
  dataset_storage_mb: number;
  conversation_count: number;
  conversation_storage_mb: number;
  total_storage_mb: number;
  percentage: number;
}

const COLORS = ['#2563eb', '#3b82f6', '#60a5fa', '#93c5fd', '#bfdbfe', '#dbeafe', '#eff6ff', '#1e40af'];

function getFilterLabel(userId: string, datasetId: string): string {
  return (userId || datasetId) ? 'Per Selection' : 'All Users/Datasets';
}

interface StorageBreakdownProps {
  observabilityMode: 'individual' | 'team';
  teamId?: string;
  isTeamObserver: boolean;
}

export function StorageBreakdown({ observabilityMode, teamId, isTeamObserver }: StorageBreakdownProps) {
  const [overview, setOverview] = useState<StorageOverview | null>(null);
  const [users, setUsers] = useState<UserListItem[]>([]);
  const [datasets, setDatasets] = useState<Array<{id: string; name: string; created_by: string}>>([]);
  const [filteredDatasets, setFilteredDatasets] = useState<Array<{id: string; name: string; created_by: string}>>([]);
  const [selectedUserId, setSelectedUserId] = useState<string>('');
  const [selectedDatasetId, setSelectedDatasetId] = useState<string>('');
  const [fileTypeData, setFileTypeData] = useState<FileTypeBreakdown[]>([]);
  const [fileDetailsData, setFileDetailsData] = useState<DatasetFileDetails[]>([]);
  const [expandedDatasets, setExpandedDatasets] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isAdmin, setIsAdmin] = useState(false);
  const [userStorageData, setUserStorageData] = useState<UserStorageItem[]>([]);
  const [activeStorageTab, setActiveStorageTab] = useState<'total' | 'dataset' | 'conversation'>('total');

  // Check user role on mount
  useEffect(() => {
    const role = getUserRole();
    setIsAdmin(role === 'admin' || role === 'developer');
  }, []);

  useEffect(() => {
    async function fetchUsersAndDatasets() {
      try {
        // Only fetch users if admin in individual mode (endpoint is admin-only)
        if (isAdmin && observabilityMode === 'individual') {
          const usersResponse = await api.get<UserListItem[]>('/api/v1/observability/users');
          if (usersResponse.data) {
            setUsers(usersResponse.data);
          }
        }

        // Fetch datasets with ownership info from new endpoint
        // In team mode, pass team_id to get team-shared datasets only
        let datasetsUrl = '/api/v1/observability/datasets';
        if (observabilityMode === 'team' && teamId) {
          datasetsUrl += `?team_id=${teamId}`;
        }

        console.log('[StorageBreakdown] Fetching datasets from:', datasetsUrl);
        interface DatasetItem { id: string; name: string; created_by: string }
        const datasetsResponse = await api.get<DatasetItem[]>(datasetsUrl);
        if (datasetsResponse.data) {
          const datasetList = datasetsResponse.data.map((d) => ({
            id: d.id,
            name: d.name,
            created_by: d.created_by
          }));
          setDatasets(datasetList);
          setFilteredDatasets(datasetList); // Initially show all datasets
        }
      } catch (err: any) {
        console.error('Failed to fetch users and datasets:', err);
      }
    }

    // Only fetch when isAdmin state is initialized
    if (isAdmin !== undefined) {
      fetchUsersAndDatasets();
    }
  }, [isAdmin, observabilityMode, teamId]);

  // Handle user filter change
  const handleUserChange = (userId: string) => {
    console.log('[StorageBreakdown] User filter changed to:', userId);
    setSelectedUserId(userId);

    if (userId) {
      // Filter datasets to those created by this user
      const userDatasets = datasets.filter(d => d.created_by === userId);
      console.log('[StorageBreakdown] Filtered to', userDatasets.length, 'datasets created by user');
      setFilteredDatasets(userDatasets);

      // Reset dataset selection if current dataset not in filtered list
      if (selectedDatasetId && !userDatasets.find(d => d.id === selectedDatasetId)) {
        console.log('[StorageBreakdown] Clearing dataset selection (not in filtered list)');
        setSelectedDatasetId('');
      }
    } else {
      // Show all datasets
      console.log('[StorageBreakdown] Showing all datasets');
      setFilteredDatasets(datasets);
    }
  };

  useEffect(() => {
    async function fetchStorage() {
      console.log('[StorageBreakdown] Fetching storage with filters - user:', selectedUserId, 'dataset:', selectedDatasetId);

      // Use different loading states: initial load vs refresh
      if (overview === null) {
        setLoading(true);
      } else {
        setIsRefreshing(true);
      }
      setError(null);

      try {
        const params: any = {};

        // Team mode: pass team_id parameter
        if (observabilityMode === 'team' && teamId) {
          params.team_id = teamId;
          console.log('[StorageBreakdown] Added team_id param:', teamId);
        }
        // Individual mode: pass user_id for admin filtering
        else if (observabilityMode === 'individual' && selectedUserId) {
          params.user_id = selectedUserId;
          console.log('[StorageBreakdown] Added user_id param:', selectedUserId);
        }

        if (selectedDatasetId) {
          params.dataset_id = selectedDatasetId;
          console.log('[StorageBreakdown] Added dataset_id param:', selectedDatasetId);
        }

        // Request user breakdown data for the chart (admin in individual mode)
        if (isAdmin && observabilityMode === 'individual') {
          params.view = 'user';
          console.log('[StorageBreakdown] Added view=user param for user breakdown chart');
        }

        console.log('[StorageBreakdown] API params:', params);
        interface StorageResponse {
          overview?: StorageOverview;
          file_type_breakdown?: FileTypeBreakdown[];
          dataset_file_details?: DatasetFileDetails[];
          breakdown_by_user?: UserStorageItem[];
        }
        const response = await api.get<StorageResponse>('/api/v1/observability/storage', { params });
        console.log('[StorageBreakdown] API response:', response.data);

        if (response.data) {
          if (response.data.overview) {
            setOverview(response.data.overview);
          }
          // Set new visualization data
          if (response.data.file_type_breakdown) {
            console.log('[StorageBreakdown] Setting file type data:', response.data.file_type_breakdown.length, 'items');
            setFileTypeData(response.data.file_type_breakdown);
          }
          if (response.data.dataset_file_details) {
            console.log('[StorageBreakdown] Setting file details data:', response.data.dataset_file_details.length, 'datasets');
            setFileDetailsData(response.data.dataset_file_details);
          }
          if (response.data.breakdown_by_user) {
            console.log('[StorageBreakdown] Setting user storage data:', response.data.breakdown_by_user.length, 'users');
            // Sort by storage (highest first)
            setUserStorageData(
              [...response.data.breakdown_by_user].sort((a, b) => b.storage_mb - a.storage_mb)
            );
          }
        }
      } catch (err: any) {
        console.error('Failed to fetch storage breakdown:', err);
        setError(err.response?.data?.detail || 'Failed to load storage breakdown');
      } finally {
        setLoading(false);
        setIsRefreshing(false);
      }
    }

    fetchStorage();
  }, [selectedUserId, selectedDatasetId, isAdmin, observabilityMode]);

  if (loading) {
    return (
      <div className="bg-white border border-gt-gray-200 rounded-lg p-6 animate-pulse">
        <div className="h-6 bg-gt-gray-200 rounded w-48 mb-4"></div>
        <div className="h-80 bg-gt-gray-100 rounded"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-6">
        <p className="text-red-800 font-medium">Failed to load storage breakdown</p>
        <p className="text-red-600 text-sm mt-1">{error}</p>
      </div>
    );
  }

  return (
    <div className="bg-white border border-gt-gray-200 rounded-lg p-6 relative">
      {/* Subtle loading overlay during refresh */}
      {isRefreshing && (
        <div className="absolute top-0 left-0 right-0 h-1 bg-blue-100 overflow-hidden">
          <div className="h-full bg-blue-500 animate-pulse w-1/3"></div>
        </div>
      )}

      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gt-gray-900 flex items-center gap-2">
          <Database className="w-5 h-5 text-blue-600" />
          Dataset Storage ({getFilterLabel(selectedUserId, selectedDatasetId)})
        </h3>

        {/* Dual Filter Dropdowns */}
        <div className="flex items-center gap-3">
          {/* User Filter - Only show for admins in individual mode */}
          {isAdmin && observabilityMode === 'individual' && (
            <div className="flex items-center gap-2 border border-gt-gray-200 rounded-lg px-3 py-1.5">
              <User className="w-4 h-4 text-gt-gray-500" />
              <select
                value={selectedUserId}
                onChange={(e) => handleUserChange(e.target.value)}
                className="bg-transparent border-none text-sm font-medium text-gt-gray-900 cursor-pointer focus:outline-none"
              >
                <option value="">All Users</option>
                {users.map((user) => (
                  <option key={user.id} value={user.id}>
                    {user.full_name || user.email}
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Team Mode Indicator */}
          {observabilityMode === 'team' && (
            <div className="text-sm text-gt-gray-600 px-3 py-1.5 bg-blue-50 rounded-lg">
              Showing datasets shared with {teamId === 'all' ? 'all managed teams' : 'this team'}
            </div>
          )}

          {/* Dataset Filter */}
          <div className="flex items-center gap-2 border border-gt-gray-200 rounded-lg px-3 py-1.5">
            <Database className="w-4 h-4 text-gt-gray-500" />
            <select
              value={selectedDatasetId}
              onChange={(e) => setSelectedDatasetId(e.target.value)}
              className="bg-transparent border-none text-sm font-medium text-gt-gray-900 cursor-pointer focus:outline-none"
            >
              <option value="">All Datasets</option>
              {filteredDatasets.map((dataset) => (
                <option key={dataset.id} value={dataset.id}>
                  {dataset.name}
                </option>
              ))}
            </select>
          </div>

          {/* Filter Status Indicator */}
          {(selectedUserId || selectedDatasetId) && (
            <span className="text-xs text-gt-gray-600 font-medium px-2 py-1 bg-blue-50 rounded">
              {selectedUserId && selectedDatasetId ? 'Filtered (User + Dataset)' :
               selectedUserId ? 'Filtered (User)' : 'Filtered (Dataset)'}
            </span>
          )}
        </div>
      </div>

      {/* Compact Metrics */}
      {overview && (
        <div className="grid grid-cols-3 gap-4 mb-6 pb-6 border-b border-gt-gray-200">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-blue-50 rounded-lg flex items-center justify-center">
              <FileText className="w-5 h-5 text-blue-600" />
            </div>
            <div>
              <p className="text-xs text-gt-gray-600">Total Files</p>
              <p className="text-lg font-bold text-gt-gray-900">{overview.total_documents.toLocaleString()}</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-blue-50 rounded-lg flex items-center justify-center">
              <HardDrive className="w-5 h-5 text-blue-600" />
            </div>
            <div>
              <p className="text-xs text-gt-gray-600">Storage Used</p>
              <p className="text-lg font-bold text-gt-gray-900">{formatStorageSize(overview.total_storage_mb)}</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-blue-50 rounded-lg flex items-center justify-center">
              <Database className="w-5 h-5 text-blue-600" />
            </div>
            <div>
              <p className="text-xs text-gt-gray-600">Total Datasets</p>
              <p className="text-lg font-bold text-gt-gray-900">{overview.total_datasets.toLocaleString()}</p>
            </div>
          </div>
        </div>
      )}

      {/* Main Visualizations Grid */}
      <div className="grid grid-cols-12 gap-6">
        {/* File Type Distribution Donut */}
        <div className="col-span-4">
          <h4 className="text-sm font-semibold text-gt-gray-900 mb-3">File Types ({getFilterLabel(selectedUserId, selectedDatasetId)})</h4>
          {fileTypeData.length > 0 ? (
            <div className="space-y-3">
              <ResponsiveContainer width="100%" height={200}>
                <PieChart>
                  <Pie
                    data={fileTypeData}
                    cx="50%"
                    cy="50%"
                    innerRadius={50}
                    outerRadius={80}
                    dataKey="storage_mb"
                    label={false}
                  >
                    {fileTypeData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip
                    content={({ active, payload }) => {
                      if (active && payload && payload.length) {
                        const data = payload[0].payload;
                        return (
                          <div className="bg-white border border-gt-gray-200 rounded-lg p-3 shadow-lg">
                            <p className="font-medium text-gt-gray-900 mb-1">{data.file_type}</p>
                            <p className="text-sm text-gt-gray-600">{formatStorageSize(data.storage_mb)}</p>
                            <p className="text-sm text-gt-gray-600">{data.document_count} files</p>
                          </div>
                        );
                      }
                      return null;
                    }}
                  />
                </PieChart>
              </ResponsiveContainer>
              {/* Legend */}
              <div className="space-y-2">
                {fileTypeData.map((entry, index) => (
                  <div key={entry.file_type} className="flex items-center justify-between text-sm">
                    <div className="flex items-center gap-2">
                      <div
                        className="w-3 h-3 rounded-sm flex-shrink-0"
                        style={{ backgroundColor: COLORS[index % COLORS.length] }}
                      />
                      <span className="text-gt-gray-700 font-medium">{entry.file_type}</span>
                    </div>
                    <span className="text-gt-gray-600 text-xs font-mono">
                      {entry.percentage.toFixed(1)}%
                    </span>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="h-48 flex items-center justify-center text-gt-gray-500 text-sm">
              <p>No file type data</p>
            </div>
          )}
        </div>

        {/* File Sizes per Dataset */}
        <div className="col-span-8">
          <h4 className="text-sm font-semibold text-gt-gray-900 mb-3">File Sizes per Dataset ({getFilterLabel(selectedUserId, selectedDatasetId)})</h4>
          {fileDetailsData.length > 0 ? (
            <div className="space-y-2 max-h-[600px] overflow-y-auto">
              {fileDetailsData.map((dataset) => {
                const isExpanded = expandedDatasets.has(dataset.dataset_id);
                return (
                  <div key={dataset.dataset_id} className="border border-gt-gray-200 rounded-lg overflow-hidden">
                    {/* Dataset Header - Clickable */}
                    <button
                      onClick={() => {
                        const newExpanded = new Set(expandedDatasets);
                        if (isExpanded) {
                          newExpanded.delete(dataset.dataset_id);
                        } else {
                          newExpanded.add(dataset.dataset_id);
                        }
                        setExpandedDatasets(newExpanded);
                      }}
                      className="w-full px-4 py-3 bg-gt-gray-50 hover:bg-gt-gray-100 transition-colors flex items-center justify-between"
                    >
                      <div className="flex items-center gap-3">
                        <Database className="w-4 h-4 text-blue-600" />
                        <span className="font-medium text-gt-gray-900">{dataset.dataset_name}</span>
                        <span className="text-sm text-gt-gray-600">
                          ({dataset.file_count} {dataset.file_count === 1 ? 'file' : 'files'})
                        </span>
                      </div>
                      <div className="flex items-center gap-3">
                        <span className="text-sm font-semibold text-blue-600">
                          {formatStorageSize(dataset.total_size_mb)}
                        </span>
                        <LayoutGrid className={`w-4 h-4 text-gt-gray-400 transition-transform ${isExpanded ? 'rotate-180' : ''}`} />
                      </div>
                    </button>

                    {/* Expandable File List */}
                    {isExpanded && dataset.files.length > 0 && (
                      <div className="border-t border-gt-gray-200">
                        <table className="w-full text-sm">
                          <thead className="bg-gt-gray-50 border-b border-gt-gray-200">
                            <tr>
                              <th className="px-4 py-2 text-left text-xs font-semibold text-gt-gray-700">File Name</th>
                              <th className="px-4 py-2 text-left text-xs font-semibold text-gt-gray-700">Type</th>
                              <th className="px-4 py-2 text-right text-xs font-semibold text-gt-gray-700">Size</th>
                              <th className="px-4 py-2 text-right text-xs font-semibold text-gt-gray-700">Uploaded</th>
                            </tr>
                          </thead>
                          <tbody>
                            {dataset.files.map((file, idx) => (
                              <tr key={idx} className="border-b border-gt-gray-100 last:border-0 hover:bg-gt-gray-50">
                                <td className="px-4 py-2 text-gt-gray-900 font-medium">{file.file_name}</td>
                                <td className="px-4 py-2 text-gt-gray-600">{file.file_type}</td>
                                <td className="px-4 py-2 text-right text-gt-gray-900 font-mono">{formatStorageSize(file.file_size_mb)}</td>
                                <td className="px-4 py-2 text-right text-gt-gray-600">
                                  {new Date(file.uploaded_at).toLocaleDateString()}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="h-48 flex items-center justify-center text-gt-gray-500 text-sm">
              <p>No dataset file data</p>
            </div>
          )}
        </div>
      </div>

      {/* Storage Per User - Tabbed View */}
      {isAdmin && observabilityMode === 'individual' && userStorageData.length > 1 && (
        <div className="mt-6 pt-6 border-t border-gt-gray-200">
          <h4 className="text-sm font-semibold text-gt-gray-900 mb-4 flex items-center gap-2">
            <User className="w-4 h-4 text-blue-600" />
            Storage Per User
          </h4>

          <Tabs value={activeStorageTab} onValueChange={(v) => setActiveStorageTab(v as 'total' | 'dataset' | 'conversation')}>
            <TabsList className="mb-4">
              <TabsTrigger value="total" className="flex items-center gap-1.5">
                <HardDrive className="w-3.5 h-3.5" />
                Total
              </TabsTrigger>
              <TabsTrigger value="dataset" className="flex items-center gap-1.5">
                <Database className="w-3.5 h-3.5" />
                Datasets
              </TabsTrigger>
              <TabsTrigger value="conversation" className="flex items-center gap-1.5">
                <MessageSquare className="w-3.5 h-3.5" />
                Conversations
              </TabsTrigger>
            </TabsList>

            <TabsContent value={activeStorageTab} className="mt-0">
              <ResponsiveContainer width="100%" height={Math.max(200, userStorageData.length * 40 + 40)}>
                <BarChart
                  data={userStorageData.map(u => ({
                    ...u,
                    name: u.label.length > 35 ? u.label.substring(0, 35) + '...' : u.label,
                    fullName: u.label,
                    value: activeStorageTab === 'dataset' ? u.dataset_storage_mb :
                           activeStorageTab === 'conversation' ? u.conversation_storage_mb :
                           u.total_storage_mb
                  }))}
                  layout="vertical"
                  margin={{ top: 5, right: 30, left: 120, bottom: 5 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" horizontal={false} />
                  <XAxis
                    type="number"
                    stroke="#6b7280"
                    style={{ fontSize: '12px' }}
                    tickFormatter={(value) => formatStorageSize(value)}
                  />
                  <YAxis
                    type="category"
                    dataKey="name"
                    width={115}
                    stroke="#6b7280"
                    tick={{ fontSize: 11 }}
                  />
                  <Tooltip
                    content={({ active, payload }) => {
                      if (active && payload && payload.length) {
                        const data = payload[0].payload;
                        return (
                          <div className="bg-white border border-gt-gray-200 rounded-lg p-3 shadow-lg">
                            <p className="font-medium text-gt-gray-900 mb-2">{data.fullName}</p>

                            {activeStorageTab === 'dataset' && (
                              <>
                                <p className="text-sm text-gt-gray-600">
                                  <span className="font-medium text-blue-600">{formatStorageSize(data.dataset_storage_mb)}</span> storage
                                </p>
                                <p className="text-sm text-gt-gray-600">
                                  <span className="font-medium">{data.document_count}</span> documents
                                </p>
                              </>
                            )}

                            {activeStorageTab === 'conversation' && (
                              <>
                                <p className="text-sm text-gt-gray-600">
                                  <span className="font-medium text-purple-600">{formatStorageSize(data.conversation_storage_mb)}</span> storage
                                </p>
                                <p className="text-sm text-gt-gray-600">
                                  <span className="font-medium">{data.conversation_count}</span> conversations
                                </p>
                              </>
                            )}

                            {activeStorageTab === 'total' && (
                              <>
                                <p className="text-sm text-gt-gray-600">
                                  <span className="font-medium text-green-600">{formatStorageSize(data.total_storage_mb)}</span> total
                                </p>
                                <p className="text-sm text-gt-gray-500 text-xs mt-1">
                                  Dataset: {formatStorageSize(data.dataset_storage_mb)} | Conv: {formatStorageSize(data.conversation_storage_mb)}
                                </p>
                                <p className="text-sm text-gt-gray-500 mt-1">{data.percentage.toFixed(1)}% of total</p>
                              </>
                            )}
                          </div>
                        );
                      }
                      return null;
                    }}
                  />
                  <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                    {userStorageData.map((_, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </TabsContent>
          </Tabs>
        </div>
      )}
    </div>
  );
}
