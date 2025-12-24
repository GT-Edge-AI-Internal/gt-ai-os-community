'use client';

import { useState } from 'react';
import { X, Download, FileText, FileJson, CheckCircle } from 'lucide-react';
import { ObservabilityFilters } from './observability-dashboard';
import { getAuthToken, getTenantInfo } from '@/services/auth';

interface ExportModalProps {
  filters: ObservabilityFilters;
  onClose: () => void;
  mode?: 'single' | 'filtered' | 'all';
  conversationId?: string;
  conversationTitle?: string;
  searchQuery?: string;
}

export function ExportModal({ filters, onClose, mode = 'all', conversationId, conversationTitle, searchQuery }: ExportModalProps) {
  const [format, setFormat] = useState<'csv' | 'json'>('csv');
  const [includeContent, setIncludeContent] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [success, setSuccess] = useState(false);

  async function handleExport() {
    setExporting(true);
    setSuccess(false);

    try {
      const token = getAuthToken();
      const tenantInfo = getTenantInfo();

      const params = new URLSearchParams({
        format,
        include_content: includeContent.toString()
      });

      // Handle date range - custom vs preset vs specific date
      if (filters.specificDate) {
        // Specific date filter (from chart click)
        params.append('specific_date', filters.specificDate);
      } else if (filters.dateRange === 'custom' && filters.startDate && filters.endDate) {
        // Combine date + time into ISO timestamps (add :00 seconds since time input is HH:MM)
        const startDateTime = `${filters.startDate}T${filters.startTime ? filters.startTime + ':00' : '00:00:00'}Z`;
        const endDateTime = `${filters.endDate}T${filters.endTime ? filters.endTime + ':00' : '23:59:59'}Z`;
        params.append('start_date', startDateTime);
        params.append('end_date', endDateTime);
      } else if (filters.dateRange !== 'custom' && filters.dateRange !== 'all') {
        params.append('days', filters.dateRange.toString());
      }
      // For 'all', don't send any date parameters

      // Add mode-specific parameters
      if (mode === 'single' && conversationId) {
        params.append('conversation_id', conversationId);
      } else {
        // For 'filtered' and 'all' modes, include filters
        if (filters.userId) params.append('user_id', filters.userId);
        if (filters.agentId) params.append('agent_id', filters.agentId);
        if (searchQuery) params.append('search', searchQuery);
      }

      const headers: Record<string, string> = {
        'Content-Type': 'application/json'
      };

      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }

      if (tenantInfo?.domain) {
        headers['X-Tenant-Domain'] = tenantInfo.domain;
      }

      // Make the request and get the blob
      const response = await fetch(
        `/api/v1/observability/export?${params.toString()}`,
        {
          headers
        }
      );

      if (!response.ok) {
        throw new Error('Export failed');
      }

      // Get the filename from Content-Disposition header or generate one
      const contentDisposition = response.headers.get('Content-Disposition');
      let filename = `analytics_export_${new Date().toISOString().split('T')[0]}.${format}`;

      if (contentDisposition) {
        const filenameMatch = contentDisposition.match(/filename="?(.+)"?/);
        if (filenameMatch) {
          filename = filenameMatch[1];
        }
      }

      // Create blob and trigger download
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);

      setSuccess(true);
      setTimeout(() => {
        onClose();
      }, 1500);
    } catch (err: any) {
      console.error('Export failed:', err);
      alert('Failed to export data. Please try again.');
    } finally {
      setExporting(false);
    }
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-gt-white rounded-lg shadow-xl max-w-md w-full">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gt-gray-200">
          <div>
            <h2 className="text-xl font-bold text-gt-gray-900 flex items-center gap-2">
              <Download className="w-5 h-5 text-gt-green" />
              Export {mode === 'single' ? 'Conversation' : mode === 'filtered' ? 'Filtered Results' : 'Analytics Data'}
            </h2>
            {mode === 'single' && conversationTitle && (
              <p className="text-sm text-gt-gray-600 mt-1">{conversationTitle}</p>
            )}
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gt-gray-100 rounded-lg transition-colors"
            disabled={exporting}
          >
            <X className="w-5 h-5 text-gt-gray-600" />
          </button>
        </div>

        {/* Body */}
        <div className="p-6 space-y-6">
          {/* Success Message */}
          {success && (
            <div className="bg-green-50 border border-green-200 rounded-lg p-4 flex items-center gap-3">
              <CheckCircle className="w-5 h-5 text-green-600 flex-shrink-0" />
              <div>
                <p className="text-green-800 font-medium">Export successful!</p>
                <p className="text-green-600 text-sm">Your download should start automatically.</p>
              </div>
            </div>
          )}

          {/* Format Selection */}
          <div>
            <label className="block text-sm font-medium text-gt-gray-900 mb-3">
              Export Format
            </label>
            <div className="grid grid-cols-2 gap-3">
              <button
                onClick={() => setFormat('csv')}
                disabled={exporting}
                className={`flex items-center gap-3 p-4 border-2 rounded-lg transition-all ${
                  format === 'csv'
                    ? 'border-gt-green bg-gt-green/5'
                    : 'border-gt-gray-200 hover:border-gt-gray-300'
                } ${exporting ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
              >
                <FileText className={`w-6 h-6 ${format === 'csv' ? 'text-gt-green' : 'text-gt-gray-400'}`} />
                <div className="text-left">
                  <div className="font-medium text-gt-gray-900">CSV</div>
                  <div className="text-xs text-gt-gray-600">Spreadsheet format</div>
                </div>
              </button>
              <button
                onClick={() => setFormat('json')}
                disabled={exporting}
                className={`flex items-center gap-3 p-4 border-2 rounded-lg transition-all ${
                  format === 'json'
                    ? 'border-gt-green bg-gt-green/5'
                    : 'border-gt-gray-200 hover:border-gt-gray-300'
                } ${exporting ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
              >
                <FileJson className={`w-6 h-6 ${format === 'json' ? 'text-gt-green' : 'text-gt-gray-400'}`} />
                <div className="text-left">
                  <div className="font-medium text-gt-gray-900">JSON</div>
                  <div className="text-xs text-gt-gray-600">Structured data</div>
                </div>
              </button>
            </div>
          </div>

          {/* Include Content Option */}
          <div>
            <label className="flex items-start gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={includeContent}
                onChange={(e) => setIncludeContent(e.target.checked)}
                disabled={exporting}
                className="mt-1 w-4 h-4 text-gt-green focus:ring-gt-green border-gt-gray-300 rounded disabled:opacity-50"
              />
              <div>
                <div className="font-medium text-gt-gray-900">Include message content</div>
                <div className="text-sm text-gt-gray-600 mt-1">
                  Export full conversation messages and content. This will significantly increase file size.
                </div>
              </div>
            </label>
          </div>

          {/* Export Info */}
          <div className="bg-gt-gray-50 rounded-lg p-4 space-y-2 text-sm">
            {mode === 'single' ? (
              <div className="flex justify-between">
                <span className="text-gt-gray-600">Export scope:</span>
                <span className="font-medium text-gt-gray-900">Single conversation</span>
              </div>
            ) : (
              <>
                <div className="flex justify-between">
                  <span className="text-gt-gray-600">Date range:</span>
                  <span className="font-medium text-gt-gray-900">
                    {filters.dateRange === 'all'
                      ? 'All Time'
                      : filters.dateRange === 'custom' && filters.startDate && filters.endDate
                        ? `${new Date(filters.startDate + 'T12:00:00').toLocaleDateString()} - ${new Date(filters.endDate + 'T12:00:00').toLocaleDateString()}`
                        : `Last ${filters.dateRange} days`
                    }
                  </span>
                </div>
                {searchQuery && (
                  <div className="flex justify-between">
                    <span className="text-gt-gray-600">Search query:</span>
                    <span className="font-medium text-gt-gray-900 truncate max-w-[200px]">{searchQuery}</span>
                  </div>
                )}
                {filters.userId && (
                  <div className="flex justify-between">
                    <span className="text-gt-gray-600">Filtered by user:</span>
                    <span className="font-medium text-gt-gray-900">Yes</span>
                  </div>
                )}
                {filters.agentId && (
                  <div className="flex justify-between">
                    <span className="text-gt-gray-600">Filtered by agent:</span>
                    <span className="font-medium text-gt-gray-900">Yes</span>
                  </div>
                )}
              </>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="p-6 border-t border-gt-gray-200 flex gap-3 justify-end">
          <button
            onClick={onClose}
            disabled={exporting}
            className="px-4 py-2 bg-gt-gray-100 text-gt-gray-700 rounded-lg hover:bg-gt-gray-200 transition-colors disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            onClick={handleExport}
            disabled={exporting || success}
            className="px-4 py-2 bg-gt-green text-white rounded-lg hover:bg-gt-green-dark transition-colors disabled:opacity-50 flex items-center gap-2"
          >
            {exporting ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                Exporting...
              </>
            ) : success ? (
              <>
                <CheckCircle className="w-4 h-4" />
                Exported
              </>
            ) : (
              <>
                <Download className="w-4 h-4" />
                Export Data
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
