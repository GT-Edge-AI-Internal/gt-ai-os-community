'use client';

import { useEffect, useState } from 'react';
import { LineChart, Line, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { ObservabilityFilters } from './observability-dashboard';
import { api } from '@/services/api';

interface TimeSeriesData {
  date: string;
  conversation_count: number;
  message_count: number;
  token_count: number;
  unique_users: number;
}

interface UsageAnalytics {
  overview: any;
  time_series: TimeSeriesData[];
}

export function UsageTimeSeries({ filters }: { filters: ObservabilityFilters }) {
  const [data, setData] = useState<TimeSeriesData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeMetric, setActiveMetric] = useState<'conversations' | 'messages' | 'tokens'>('conversations');

  useEffect(() => {
    async function fetchTimeSeries() {
      setLoading(true);
      setError(null);

      try {
        const response = await api.get<UsageAnalytics>(`/api/v1/observability/usage?days=${filters.dateRange}`);

        if (response.data && response.data.time_series) {
          setData(response.data.time_series);
        }
      } catch (err: any) {
        console.error('Failed to fetch time series data:', err);
        setError(err.response?.data?.detail || 'Failed to load time series data');
      } finally {
        setLoading(false);
      }
    }

    fetchTimeSeries();
  }, [filters]);

  if (loading) {
    return (
      <div className="bg-white border border-gt-gray-200 rounded-lg p-6">
        <div className="h-8 bg-gt-gray-200 rounded w-48 mb-6 animate-pulse"></div>
        <div className="h-80 bg-gt-gray-100 rounded animate-pulse"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-6">
        <p className="text-red-800 font-medium">Failed to load time series data</p>
        <p className="text-red-600 text-sm mt-1">{error}</p>
      </div>
    );
  }

  if (!data || data.length === 0) {
    return (
      <div className="bg-white border border-gt-gray-200 rounded-lg p-6 text-center">
        <p className="text-gt-gray-600">No activity data available for this time period</p>
      </div>
    );
  }

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  };

  const formatValue = (value: number) => {
    if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
    if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
    return value.toString();
  };

  const getMetricConfig = () => {
    switch (activeMetric) {
      case 'conversations':
        return {
          dataKey: 'conversation_count',
          name: 'Conversations',
          color: '#10b981'
        };
      case 'messages':
        return {
          dataKey: 'message_count',
          name: 'Messages',
          color: '#3b82f6'
        };
      case 'tokens':
        return {
          dataKey: 'token_count',
          name: 'Tokens',
          color: '#f59e0b'
        };
    }
  };

  const config = getMetricConfig();

  return (
    <div className="bg-white border border-gt-gray-200 rounded-lg p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold text-gt-gray-900">Usage Over Time</h2>

        {/* Metric Selector */}
        <div className="flex gap-2 bg-gt-gray-100 rounded-lg p-1">
          <button
            onClick={() => setActiveMetric('conversations')}
            className={`px-3 py-1 text-sm font-medium rounded-md transition-colors ${
              activeMetric === 'conversations'
                ? 'bg-white text-gt-gray-900 shadow-sm'
                : 'text-gt-gray-600 hover:text-gt-gray-900'
            }`}
          >
            Conversations
          </button>
          <button
            onClick={() => setActiveMetric('messages')}
            className={`px-3 py-1 text-sm font-medium rounded-md transition-colors ${
              activeMetric === 'messages'
                ? 'bg-white text-gt-gray-900 shadow-sm'
                : 'text-gt-gray-600 hover:text-gt-gray-900'
            }`}
          >
            Messages
          </button>
          <button
            onClick={() => setActiveMetric('tokens')}
            className={`px-3 py-1 text-sm font-medium rounded-md transition-colors ${
              activeMetric === 'tokens'
                ? 'bg-white text-gt-gray-900 shadow-sm'
                : 'text-gt-gray-600 hover:text-gt-gray-900'
            }`}
          >
            Tokens
          </button>
        </div>
      </div>

      {/* Chart */}
      <ResponsiveContainer width="100%" height={320}>
        <AreaChart data={data} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="colorMetric" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={config.color} stopOpacity={0.3} />
              <stop offset="95%" stopColor={config.color} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
          <XAxis
            dataKey="date"
            tickFormatter={formatDate}
            stroke="#6b7280"
            style={{ fontSize: '12px' }}
          />
          <YAxis
            tickFormatter={formatValue}
            stroke="#6b7280"
            style={{ fontSize: '12px' }}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: '#ffffff',
              border: '1px solid #e5e7eb',
              borderRadius: '8px',
              padding: '12px'
            }}
            labelFormatter={formatDate}
            formatter={(value: number) => [value.toLocaleString(), config.name]}
          />
          <Area
            type="monotone"
            dataKey={config.dataKey}
            stroke={config.color}
            strokeWidth={2}
            fill="url(#colorMetric)"
            name={config.name}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
