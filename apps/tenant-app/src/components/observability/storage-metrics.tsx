'use client';

import { useEffect, useState } from 'react';
import { FileText, HardDrive, Database } from 'lucide-react';
import { api } from '@/services/api';
import { formatStorageSize } from '@/lib/utils';

interface StorageOverview {
  total_documents: number;
  total_storage_mb: number;
  total_datasets: number;
  average_document_size_mb: number;
}

interface MetricCardProps {
  title: string;
  value: number | string;
  icon: React.ReactNode;
  format?: 'number' | 'storage';
}

function MetricCard({ title, value, icon, format = 'number' }: MetricCardProps) {
  const formattedValue = format === 'storage' && typeof value === 'number'
    ? formatStorageSize(value)
    : typeof value === 'number' ? value.toLocaleString() : value;

  return (
    <div className="bg-white border border-gt-gray-200 rounded-lg shadow-sm p-4 hover:shadow-md transition-shadow">
      <div className="flex items-center justify-between mb-3">
        <div className="w-10 h-10 bg-gt-green/10 rounded-lg flex items-center justify-center">
          {icon}
        </div>
      </div>
      <div>
        <p className="text-sm text-gt-gray-600 mb-1">{title}</p>
        <p className="text-2xl font-bold text-gt-gray-900">{formattedValue}</p>
      </div>
    </div>
  );
}


export function StorageMetrics() {
  const [data, setData] = useState<StorageOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchStorage() {
      setLoading(true);
      setError(null);

      try {
        interface StorageResponse {
          overview?: StorageOverview;
        }
        const response = await api.get<StorageResponse>('/api/v1/observability/storage');

        if (response.data && response.data.overview) {
          setData(response.data.overview);
        }
      } catch (err: any) {
        console.error('Failed to fetch storage metrics:', err);
        setError(err.response?.data?.detail || 'Failed to load storage metrics');
      } finally {
        setLoading(false);
      }
    }

    fetchStorage();
  }, []);

  if (loading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="bg-white border border-gt-gray-200 rounded-lg p-6 animate-pulse">
            <div className="w-12 h-12 bg-gt-gray-200 rounded-lg mb-4"></div>
            <div className="h-4 bg-gt-gray-200 rounded w-24 mb-2"></div>
            <div className="h-8 bg-gt-gray-200 rounded w-32"></div>
          </div>
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-6">
        <p className="text-red-800 font-medium">Failed to load storage metrics</p>
        <p className="text-red-600 text-sm mt-1">{error}</p>
      </div>
    );
  }

  if (!data) {
    return null;
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      <MetricCard
        title="Total Files"
        value={data.total_documents}
        icon={<FileText className="w-6 h-6 text-gt-green" />}
        format="number"
      />
      <MetricCard
        title="Storage Used"
        value={data.total_storage_mb}
        icon={<HardDrive className="w-6 h-6 text-gt-green" />}
        format="storage"
      />
      <MetricCard
        title="Total Datasets"
        value={data.total_datasets}
        icon={<Database className="w-6 h-6 text-gt-green" />}
        format="number"
      />
    </div>
  );
}
