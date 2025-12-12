'use client';

import { useEffect, useState } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import { Users, Bot, Cpu } from 'lucide-react';
import { ObservabilityFilters } from './observability-dashboard';
import { api } from '@/services/api';

interface BreakdownItem {
  id: string;
  label: string;
  value: number;
  percentage: number;
  metadata?: {
    tokens?: number;
  };
}

interface UsageAnalytics {
  breakdown_by_user: BreakdownItem[];
  breakdown_by_agent: BreakdownItem[];
  breakdown_by_model: BreakdownItem[];
}

const COLORS = ['#10b981', '#3b82f6', '#f59e0b', '#8b5cf6', '#ec4899', '#14b8a6', '#f97316', '#6366f1'];

export function UsageBreakdowns({ filters }: { filters: ObservabilityFilters }) {
  const [data, setData] = useState<UsageAnalytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchBreakdowns() {
      setLoading(true);
      setError(null);

      try {
        const response = await api.get<{ overview: any; time_series: any[]; breakdown_by_user: BreakdownItem[]; breakdown_by_agent: BreakdownItem[]; breakdown_by_model: BreakdownItem[] }>(
          `/api/v1/observability/usage?days=${filters.dateRange}`
        );

        if (response.data) {
          setData({
            breakdown_by_user: response.data.breakdown_by_user,
            breakdown_by_agent: response.data.breakdown_by_agent,
            breakdown_by_model: response.data.breakdown_by_model
          });
        }
      } catch (err: any) {
        console.error('Failed to fetch breakdown data:', err);
        setError(err.response?.data?.detail || 'Failed to load breakdown data');
      } finally {
        setLoading(false);
      }
    }

    fetchBreakdowns();
  }, [filters]);

  if (loading) {
    return (
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="bg-white border border-gt-gray-200 rounded-lg p-6 animate-pulse">
            <div className="h-6 bg-gt-gray-200 rounded w-32 mb-4"></div>
            <div className="h-64 bg-gt-gray-100 rounded"></div>
          </div>
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-6">
        <p className="text-red-800 font-medium">Failed to load breakdown data</p>
        <p className="text-red-600 text-sm mt-1">{error}</p>
      </div>
    );
  }

  if (!data) return null;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      {/* By User */}
      <BreakdownCard
        title="By User"
        icon={<Users className="w-5 h-5 text-gt-green" />}
        data={data.breakdown_by_user.slice(0, 10)}
        valueLabel="Conversations"
      />

      {/* By Agent */}
      <BreakdownCard
        title="By Agent"
        icon={<Bot className="w-5 h-5 text-gt-green" />}
        data={data.breakdown_by_agent.slice(0, 10)}
        valueLabel="Conversations"
      />

      {/* By Model */}
      <BreakdownCard
        title="By Model"
        icon={<Cpu className="w-5 h-5 text-gt-green" />}
        data={data.breakdown_by_model.slice(0, 10)}
        valueLabel="Messages"
      />
    </div>
  );
}

interface BreakdownCardProps {
  title: string;
  icon: React.ReactNode;
  data: BreakdownItem[];
  valueLabel: string;
}

function BreakdownCard({ title, icon, data, valueLabel }: BreakdownCardProps) {
  if (!data || data.length === 0) {
    return (
      <div className="bg-white border border-gt-gray-200 rounded-lg p-6">
        <div className="flex items-center gap-2 mb-4">
          {icon}
          <h3 className="text-lg font-semibold text-gt-gray-900">{title}</h3>
        </div>
        <p className="text-gt-gray-500 text-center py-8">No data available</p>
      </div>
    );
  }

  return (
    <div className="bg-white border border-gt-gray-200 rounded-lg p-6">
      {/* Header */}
      <div className="flex items-center gap-2 mb-4">
        {icon}
        <h3 className="text-lg font-semibold text-gt-gray-900">{title}</h3>
      </div>

      {/* Bar Chart */}
      <ResponsiveContainer width="100%" height={240}>
        <BarChart data={data} layout="vertical" margin={{ top: 5, right: 30, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" horizontal={false} />
          <XAxis type="number" stroke="#6b7280" style={{ fontSize: '12px' }} />
          <YAxis
            type="category"
            dataKey="label"
            width={100}
            stroke="#6b7280"
            style={{ fontSize: '11px' }}
            tickFormatter={(value) => value.length > 15 ? `${value.substring(0, 15)}...` : value}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: '#ffffff',
              border: '1px solid #e5e7eb',
              borderRadius: '8px',
              padding: '12px'
            }}
            formatter={(value: number, name: string, props: any) => [
              <>
                <div>{value.toLocaleString()} {valueLabel}</div>
                <div className="text-xs text-gt-gray-500 mt-1">
                  {props.payload.percentage.toFixed(1)}% of total
                </div>
                {props.payload.metadata?.tokens && (
                  <div className="text-xs text-gt-gray-500">
                    {props.payload.metadata.tokens.toLocaleString()} tokens
                  </div>
                )}
              </>,
              ''
            ]}
            labelFormatter={(value) => value}
          />
          <Bar dataKey="value" radius={[0, 4, 4, 0]}>
            {data.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      {/* Legend/List */}
      <div className="mt-4 space-y-2 max-h-48 overflow-y-auto">
        {data.slice(0, 5).map((item, index) => (
          <div key={item.id} className="flex items-center justify-between text-sm">
            <div className="flex items-center gap-2 flex-1 min-w-0">
              <div
                className="w-3 h-3 rounded-full flex-shrink-0"
                style={{ backgroundColor: COLORS[index % COLORS.length] }}
              />
              <span className="text-gt-gray-700 truncate" title={item.label}>
                {item.label}
              </span>
            </div>
            <div className="flex items-center gap-3 text-gt-gray-600 flex-shrink-0 ml-2">
              <span className="font-medium">{item.value.toLocaleString()}</span>
              <span className="text-xs">({item.percentage.toFixed(1)}%)</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
