'use client';

import { useEffect, useState } from 'react';
import { MessageSquare, FileText, Zap, Users, TrendingUp, TrendingDown } from 'lucide-react';
import { ObservabilityFilters } from './observability-dashboard';
import { api } from '@/services/api';

interface OverviewData {
  total_conversations: number;
  total_messages: number;
  total_tokens: number;
  unique_users: number;
  date_range_start: string;
  date_range_end: string;
}

interface MetricCardProps {
  title: string;
  value: number | string;
  icon: React.ReactNode;
  trend?: number;
  format?: 'number' | 'abbreviated';
}

function MetricCard({ title, value, icon, trend, format = 'number' }: MetricCardProps) {
  const formattedValue = format === 'abbreviated' && typeof value === 'number'
    ? formatNumber(value)
    : value.toLocaleString();

  return (
    <div className="bg-gt-white border border-gt-gray-200 rounded-lg shadow-sm p-4 hover:shadow-md transition-shadow">
      <div className="flex items-center justify-between mb-3">
        <div className="w-10 h-10 bg-gt-green/10 rounded-lg flex items-center justify-center">
          {icon}
        </div>
        {trend !== undefined && (
          <div className={`flex items-center gap-1 text-sm font-medium ${
            trend >= 0 ? 'text-green-600' : 'text-red-600'
          }`}>
            {trend >= 0 ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
            {Math.abs(trend)}%
          </div>
        )}
      </div>
      <div>
        <p className="text-sm text-gt-gray-600 mb-1">{title}</p>
        <p className="text-2xl font-bold text-gt-gray-900">{formattedValue}</p>
      </div>
    </div>
  );
}

function formatNumber(num: number): string {
  if (num >= 1_000_000) {
    return `${(num / 1_000_000).toFixed(1)}M`;
  } else if (num >= 1_000) {
    return `${(num / 1_000).toFixed(1)}K`;
  }
  return num.toString();
}

export function OverviewMetrics({ filters }: { filters: ObservabilityFilters }) {
  const [data, setData] = useState<OverviewData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchOverview() {
      setLoading(true);
      setError(null);

      try {
        const response = await api.get(`/api/v1/observability/overview?days=${filters.dateRange}`);

        if (response.data) {
          setData(response.data);
        }
      } catch (err: any) {
        console.error('Failed to fetch overview metrics:', err);
        setError(err.response?.data?.detail || 'Failed to load analytics data');
      } finally {
        setLoading(false);
      }
    }

    fetchOverview();
  }, [filters]);

  if (loading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="bg-gt-white border border-gt-gray-200 rounded-lg p-6 animate-pulse">
            <div className="w-12 h-12 bg-gt-gray-200 rounded-lg mb-4"></div>
            <div className="h-4 bg-gt-gray-200 rounded w-24 mb-2"></div>
            <div className="h-8 bg-gt-gray-200 rounded w-16"></div>
          </div>
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
        <p className="text-red-800 font-medium">Failed to load overview metrics</p>
        <p className="text-red-600 text-sm mt-1">{error}</p>
      </div>
    );
  }

  if (!data) {
    return null;
  }

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      <MetricCard
        title="Total Conversations"
        value={data.total_conversations}
        icon={<MessageSquare className="w-6 h-6 text-gt-green" />}
        format="number"
      />
      <MetricCard
        title="Total Messages"
        value={data.total_messages}
        icon={<FileText className="w-6 h-6 text-gt-green" />}
        format="abbreviated"
      />
      <MetricCard
        title="Tokens Consumed"
        value={data.total_tokens}
        icon={<Zap className="w-6 h-6 text-gt-green" />}
        format="abbreviated"
      />
      <MetricCard
        title="Active Users"
        value={data.unique_users}
        icon={<Users className="w-6 h-6 text-gt-green" />}
        format="number"
      />
    </div>
  );
}
