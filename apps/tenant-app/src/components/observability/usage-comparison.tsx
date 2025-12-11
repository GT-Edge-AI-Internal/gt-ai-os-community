'use client';

import { useState } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend, Cell } from 'recharts';
import { Bot, Cpu } from 'lucide-react';

interface BreakdownItem {
  id: string;
  label: string;
  value: number;
  percentage: number;
  metadata?: {
    tokens?: number;
  };
}

interface UsageComparisonProps {
  agentData: BreakdownItem[];
  modelData: BreakdownItem[];
}

const COLORS = ['#10b981', '#3b82f6', '#f59e0b', '#8b5cf6', '#ec4899', '#14b8a6', '#f97316', '#6366f1'];

export function UsageComparison({ agentData, modelData }: UsageComparisonProps) {
  const [compareMode, setCompareMode] = useState<'agents' | 'models'>('agents');

  const currentData = compareMode === 'agents' ? agentData : modelData;
  const top10Data = currentData.slice(0, 10);

  // Transform data for side-by-side comparison
  const chartData = top10Data.map(item => ({
    name: item.label.length > 60 ? item.label.substring(0, 60) + '...' : item.label,
    fullName: item.label,
    conversations: item.value,
    tokens: item.metadata?.tokens || 0,
    percentage: item.percentage
  }));

  const CustomTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      return (
        <div className="bg-white border border-gt-gray-200 rounded-lg p-3 shadow-lg">
          <p className="font-medium text-gt-gray-900 mb-2">{data.fullName}</p>
          <p className="text-sm text-gt-gray-600">
            <span className="font-medium text-gt-green">{data.conversations.toLocaleString()}</span> conversations
          </p>
          <p className="text-sm text-gt-gray-600">
            <span className="font-medium text-blue-600">{data.tokens.toLocaleString()}</span> tokens
          </p>
          <p className="text-sm text-gt-gray-500 mt-1">{data.percentage.toFixed(1)}% of total</p>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="bg-white border border-gt-gray-200 rounded-lg p-6">
      {/* Header with Toggle */}
      <div className="flex items-center justify-between mb-6">
        <h3 className="text-lg font-semibold text-gt-gray-900 flex items-center gap-2">
          {compareMode === 'agents' ? (
            <>
              <Bot className="w-5 h-5 text-gt-green" />
              Usage by Agent
            </>
          ) : (
            <>
              <Cpu className="w-5 h-5 text-blue-600" />
              Usage by Model
            </>
          )}
        </h3>

        {/* Toggle Switch */}
        <div className="flex items-center gap-2 bg-gt-gray-100 rounded-lg p-1">
          <button
            onClick={() => setCompareMode('agents')}
            className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${
              compareMode === 'agents'
                ? 'bg-white text-gt-green shadow-sm'
                : 'text-gt-gray-600 hover:text-gt-gray-900'
            }`}
          >
            Agents
          </button>
          <button
            onClick={() => setCompareMode('models')}
            className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${
              compareMode === 'models'
                ? 'bg-white text-blue-600 shadow-sm'
                : 'text-gt-gray-600 hover:text-gt-gray-900'
            }`}
          >
            Models
          </button>
        </div>
      </div>

      {/* Chart */}
      {chartData.length > 0 ? (
        <ResponsiveContainer width="100%" height={320}>
          <BarChart
            data={chartData}
            layout="vertical"
            margin={{ top: 5, right: 30, left: 360, bottom: 5 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
            <XAxis type="number" stroke="#6b7280" />
            <YAxis
              type="category"
              dataKey="fullName"
              stroke="#6b7280"
              width={350}
              tick={{ fontSize: 11 }}
              interval={0}
            />
            <Tooltip content={<CustomTooltip />} />
            <Legend
              wrapperStyle={{ paddingTop: '20px' }}
              iconType="circle"
            />
            <Bar
              dataKey="conversations"
              fill={compareMode === 'agents' ? '#10b981' : '#3b82f6'}
              name="Conversations"
              radius={[0, 4, 4, 0]}
            >
              {chartData.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
              ))}
            </Bar>
            <Bar
              dataKey="tokens"
              fill={compareMode === 'agents' ? '#059669' : '#2563eb'}
              name="Tokens (thousands)"
              radius={[0, 4, 4, 0]}
            />
          </BarChart>
        </ResponsiveContainer>
      ) : (
        <div className="h-64 flex items-center justify-center text-gt-gray-500">
          <p>No {compareMode} data available</p>
        </div>
      )}

      {/* Top Items Summary */}
      {chartData.length > 0 && (
        <div className="mt-6 pt-6 border-t border-gt-gray-200">
          <h4 className="text-sm font-medium text-gt-gray-700 mb-3">
            Top 5 {compareMode === 'agents' ? 'Agents' : 'Models'}
          </h4>
          <div className="grid grid-cols-1 gap-2">
            {chartData.slice(0, 5).map((item, index) => (
              <div
                key={index}
                className="flex items-center justify-between py-2 px-3 rounded bg-gt-gray-50 hover:bg-gt-gray-100 transition-colors"
              >
                <div className="flex items-center gap-2 flex-1 min-w-0">
                  <div
                    className="w-3 h-3 rounded-full flex-shrink-0"
                    style={{ backgroundColor: COLORS[index % COLORS.length] }}
                  />
                  <span className="text-sm font-medium text-gt-gray-900 truncate">
                    {item.fullName}
                  </span>
                </div>
                <div className="flex items-center gap-4 text-sm text-gt-gray-600">
                  <span>{item.conversations} conv</span>
                  <span className="text-xs text-gt-gray-500">{item.percentage.toFixed(1)}%</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
