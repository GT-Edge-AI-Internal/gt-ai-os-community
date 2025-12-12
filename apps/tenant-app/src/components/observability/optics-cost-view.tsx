'use client';

import { useEffect, useState } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell, PieChart, Pie } from 'recharts';
import { DollarSign, Cpu, Database, HardDrive, TrendingUp, AlertCircle, ChevronDown } from 'lucide-react';
import { api } from '@/services/api';
import { getUserRole } from '@/lib/permissions';
import { formatStorageSize } from '@/lib/utils';

interface UserOption {
  id: string;
  email: string;
}

interface ModelCostBreakdown {
  model_id: string;
  model_name: string;
  tokens: number;
  conversations: number;
  messages: number;
  cost_cents: number;
  cost_display: string;
  percentage: number;
}

interface OpticsCostData {
  enabled: boolean;
  inference_cost_cents: number;
  storage_cost_cents: number;
  total_cost_cents: number;
  inference_cost_display: string;
  storage_cost_display: string;
  total_cost_display: string;
  total_tokens: number;
  total_storage_mb: number;
  document_count: number;
  dataset_count: number;
  by_model: ModelCostBreakdown[];
  period_start: string;
  period_end: string;
}

interface OpticsSettings {
  enabled: boolean;
  storage_cost_per_mb_cents: number;
  show_to_admins_only: boolean;
}

const COLORS = ['#10B981', '#3B82F6', '#8B5CF6', '#F59E0B', '#EF4444', '#06B6D4', '#EC4899', '#6366F1'];

function formatCurrency(cents: number): string {
  const dollars = cents / 100;
  return `$${dollars.toFixed(2)}`;
}

function formatTokens(tokens: number): string {
  if (tokens >= 1000000) {
    return `${(tokens / 1000000).toFixed(2)}M`;
  }
  if (tokens >= 1000) {
    return `${(tokens / 1000).toFixed(1)}K`;
  }
  return tokens.toString();
}

type DateRange = 7 | 30 | 90 | 365;

export function OpticsCostView() {
  const [settings, setSettings] = useState<OpticsSettings | null>(null);
  const [costData, setCostData] = useState<OpticsCostData | null>(null);
  const [dateRange, setDateRange] = useState<DateRange>(30);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isAdmin, setIsAdmin] = useState(false);
  const [users, setUsers] = useState<UserOption[]>([]);
  const [selectedUserId, setSelectedUserId] = useState<string | undefined>(undefined);

  // Check user role on mount
  useEffect(() => {
    const role = getUserRole();
    setIsAdmin(role === 'admin' || role === 'developer');
  }, []);

  // Fetch users list for admin filter dropdown
  useEffect(() => {
    async function fetchUsers() {
      if (!isAdmin) return;

      try {
        const response = await api.get('/api/v1/observability/filters');
        if (response.data?.users) {
          setUsers(response.data.users.map((u: any) => ({
            id: u.id,
            email: u.email
          })));
        }
      } catch (err) {
        console.error('Failed to fetch users for filter:', err);
      }
    }
    fetchUsers();
  }, [isAdmin]);

  // Fetch Optics settings to check if enabled
  useEffect(() => {
    async function fetchSettings() {
      try {
        const response = await api.get('/api/v1/optics/settings');
        if (response.data) {
          setSettings(response.data);
        }
      } catch (err: any) {
        console.error('Failed to fetch Optics settings:', err);
        setError('Failed to load Optics settings');
      }
    }
    fetchSettings();
  }, []);

  // Fetch cost data
  useEffect(() => {
    async function fetchCostData() {
      if (!settings?.enabled) return;

      setLoading(true);
      setError(null);

      try {
        const params: { days: number; user_id?: string } = { days: dateRange };
        if (selectedUserId) {
          params.user_id = selectedUserId;
        }
        const response = await api.get('/api/v1/optics/costs', { params });
        if (response.data) {
          setCostData(response.data);
        }
      } catch (err: any) {
        console.error('Failed to fetch Optics costs:', err);
        setError(err.response?.data?.detail || 'Failed to load cost data');
      } finally {
        setLoading(false);
      }
    }

    if (settings?.enabled) {
      fetchCostData();
    } else {
      setLoading(false);
    }
  }, [settings?.enabled, dateRange, selectedUserId]);

  // Show disabled state
  if (settings && !settings.enabled) {
    return (
      <div className="bg-white border border-gt-gray-200 rounded-lg p-8 text-center">
        <AlertCircle className="w-12 h-12 text-gt-gray-400 mx-auto mb-4" />
        <h3 className="text-lg font-semibold text-gt-gray-900 mb-2">Optics Not Enabled</h3>
        <p className="text-gt-gray-600 max-w-md mx-auto">
          Optics cost tracking is not enabled for this tenant.
          Contact your administrator to enable cost visibility.
        </p>
      </div>
    );
  }

  if (loading && !costData) {
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
        <p className="text-red-800 font-medium">Failed to load cost data</p>
        <p className="text-red-600 text-sm mt-1">{error}</p>
      </div>
    );
  }

  if (!costData) return null;

  return (
    <div className="space-y-6">
      {/* Header with Date Range */}
      <div className="bg-white border border-gt-gray-200 rounded-lg p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gt-gray-900 flex items-center gap-2">
            <DollarSign className="w-5 h-5 text-green-600" />
            Cost Overview
          </h3>
          <div className="flex items-center gap-4">
            {/* User Filter Dropdown (Admin Only) */}
            {isAdmin && users.length > 0 && (
              <div className="relative">
                <select
                  value={selectedUserId || ''}
                  onChange={(e) => setSelectedUserId(e.target.value || undefined)}
                  className="appearance-none bg-white border border-gt-gray-200 rounded-lg px-3 py-1.5 pr-8 text-sm text-gt-gray-700 hover:border-gt-gray-300 focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-transparent cursor-pointer"
                >
                  <option value="">All Users</option>
                  {users.map((user) => (
                    <option key={user.id} value={user.id}>
                      {user.email}
                    </option>
                  ))}
                </select>
                <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 w-4 h-4 text-gt-gray-400 pointer-events-none" />
              </div>
            )}
            {/* Date Range Buttons */}
            <div className="flex items-center gap-2">
              {([7, 30, 90, 365] as DateRange[]).map((days) => (
                <button
                  key={days}
                  onClick={() => setDateRange(days)}
                  className={`px-3 py-1.5 text-sm rounded-lg transition-colors ${
                    dateRange === days
                      ? 'bg-green-100 text-green-700 font-medium'
                      : 'bg-gt-gray-100 text-gt-gray-600 hover:bg-gt-gray-200'
                  }`}
                >
                  {days === 365 ? '1 Year' : `${days} Days`}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Cost Summary Cards */}
        <div className="grid grid-cols-4 gap-4">
          <div className="bg-gradient-to-br from-green-50 to-green-100 rounded-xl p-4 border border-green-200">
            <div className="flex items-center gap-3 mb-2">
              <div className="w-10 h-10 bg-green-200 rounded-lg flex items-center justify-center">
                <DollarSign className="w-5 h-5 text-green-700" />
              </div>
              <span className="text-sm font-medium text-green-700">Total Cost</span>
            </div>
            <p className="text-2xl font-bold text-green-800">{costData.total_cost_display}</p>
          </div>

          <div className="bg-gradient-to-br from-blue-50 to-blue-100 rounded-xl p-4 border border-blue-200">
            <div className="flex items-center gap-3 mb-2">
              <div className="w-10 h-10 bg-blue-200 rounded-lg flex items-center justify-center">
                <Cpu className="w-5 h-5 text-blue-700" />
              </div>
              <span className="text-sm font-medium text-blue-700">Inference</span>
            </div>
            <p className="text-2xl font-bold text-blue-800">{costData.inference_cost_display}</p>
            <p className="text-xs text-blue-600 mt-1">{formatTokens(costData.total_tokens)} tokens</p>
          </div>

          <div className="bg-gradient-to-br from-purple-50 to-purple-100 rounded-xl p-4 border border-purple-200">
            <div className="flex items-center gap-3 mb-2">
              <div className="w-10 h-10 bg-purple-200 rounded-lg flex items-center justify-center">
                <HardDrive className="w-5 h-5 text-purple-700" />
              </div>
              <span className="text-sm font-medium text-purple-700">Storage</span>
            </div>
            <p className="text-2xl font-bold text-purple-800">{costData.storage_cost_display}</p>
            <p className="text-xs text-purple-600 mt-1">{formatStorageSize(costData.total_storage_mb)}</p>
          </div>

          <div className="bg-gradient-to-br from-amber-50 to-amber-100 rounded-xl p-4 border border-amber-200">
            <div className="flex items-center gap-3 mb-2">
              <div className="w-10 h-10 bg-amber-200 rounded-lg flex items-center justify-center">
                <Database className="w-5 h-5 text-amber-700" />
              </div>
              <span className="text-sm font-medium text-amber-700">Resources</span>
            </div>
            <p className="text-2xl font-bold text-amber-800">{costData.document_count}</p>
            <p className="text-xs text-amber-600 mt-1">{costData.dataset_count} datasets</p>
          </div>
        </div>
      </div>

      {/* Visualizations Grid */}
      <div className="grid grid-cols-12 gap-6">
        {/* Cost by Model - Pie Chart */}
        <div className="col-span-5 bg-white border border-gt-gray-200 rounded-lg p-6">
          <h4 className="text-sm font-semibold text-gt-gray-900 mb-4 flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-green-600" />
            Inference Cost by Model
          </h4>
          {costData.by_model.length > 0 ? (
            <div className="space-y-4">
              <ResponsiveContainer width="100%" height={220}>
                <PieChart>
                  <Pie
                    data={costData.by_model}
                    cx="50%"
                    cy="50%"
                    innerRadius={50}
                    outerRadius={80}
                    dataKey="cost_cents"
                    label={false}
                  >
                    {costData.by_model.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip
                    content={({ active, payload }) => {
                      if (active && payload && payload.length) {
                        const data = payload[0].payload as ModelCostBreakdown;
                        return (
                          <div className="bg-white border border-gt-gray-200 rounded-lg p-3 shadow-lg">
                            <p className="font-medium text-gt-gray-900 mb-1">{data.model_name}</p>
                            <p className="text-sm text-green-600 font-semibold">{data.cost_display}</p>
                            <p className="text-xs text-gt-gray-600">{formatTokens(data.tokens)} tokens</p>
                            <p className="text-xs text-gt-gray-600">{data.conversations} conversations</p>
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
                {costData.by_model.map((model, index) => (
                  <div key={model.model_id} className="flex items-center justify-between text-sm">
                    <div className="flex items-center gap-2">
                      <div
                        className="w-3 h-3 rounded-sm flex-shrink-0"
                        style={{ backgroundColor: COLORS[index % COLORS.length] }}
                      />
                      <span className="text-gt-gray-700 font-medium truncate max-w-[150px]" title={model.model_name}>
                        {model.model_name}
                      </span>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-green-600 font-medium">{model.cost_display}</span>
                      <span className="text-gt-gray-500 text-xs font-mono w-12 text-right">
                        {model.percentage.toFixed(1)}%
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="h-48 flex items-center justify-center text-gt-gray-500 text-sm">
              <p>No inference data for this period</p>
            </div>
          )}
        </div>

        {/* Cost by Model - Bar Chart */}
        <div className="col-span-7 bg-white border border-gt-gray-200 rounded-lg p-6">
          <h4 className="text-sm font-semibold text-gt-gray-900 mb-4 flex items-center gap-2">
            <Cpu className="w-4 h-4 text-blue-600" />
            Token Usage by Model
          </h4>
          {costData.by_model.length > 0 ? (
            <ResponsiveContainer width="100%" height={320}>
              <BarChart
                data={costData.by_model}
                layout="vertical"
                margin={{ top: 5, right: 30, left: 100, bottom: 5 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
                <XAxis
                  type="number"
                  tickFormatter={(value) => formatTokens(value)}
                  tick={{ fontSize: 12, fill: '#6B7280' }}
                />
                <YAxis
                  type="category"
                  dataKey="model_name"
                  tick={{ fontSize: 12, fill: '#374151' }}
                  width={95}
                />
                <Tooltip
                  content={({ active, payload }) => {
                    if (active && payload && payload.length) {
                      const data = payload[0].payload as ModelCostBreakdown;
                      return (
                        <div className="bg-white border border-gt-gray-200 rounded-lg p-3 shadow-lg">
                          <p className="font-medium text-gt-gray-900 mb-1">{data.model_name}</p>
                          <p className="text-sm text-blue-600">{formatTokens(data.tokens)} tokens</p>
                          <p className="text-sm text-green-600">{data.cost_display}</p>
                          <p className="text-xs text-gt-gray-600">{data.messages} messages</p>
                        </div>
                      );
                    }
                    return null;
                  }}
                />
                <Bar dataKey="tokens" radius={[0, 4, 4, 0]}>
                  {costData.by_model.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-48 flex items-center justify-center text-gt-gray-500 text-sm">
              <p>No token usage data for this period</p>
            </div>
          )}
        </div>
      </div>

      {/* Period Info */}
      <div className="text-center text-xs text-gt-gray-500">
        Data from {new Date(costData.period_start).toLocaleDateString()} to {new Date(costData.period_end).toLocaleDateString()}
        <span className="mx-2">•</span>
        Storage rate: ${(settings?.storage_cost_per_mb_cents || 4) / 100}/MB
      </div>
    </div>
  );
}
