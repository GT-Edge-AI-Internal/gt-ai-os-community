'use client';

import { useState } from 'react';
import { Download, ChevronDown, FileText, FileSpreadsheet, File } from 'lucide-react';
import { downloadContent, suggestFormat, getFormatDescription, type DownloadOptions } from '@/lib/download-utils';

interface DownloadButtonProps {
  content: string;
  filename?: string;
  title?: string;
  className?: string;
}

export function DownloadButton({ content, filename, title, className = '' }: DownloadButtonProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const [downloadStatus, setDownloadStatus] = useState<string>('');
  const [error, setError] = useState<string | null>(null);

  const suggestedFormats = suggestFormat(content);

  const handleDownload = async (format: DownloadOptions['format']) => {
    setIsDownloading(true);
    setDownloadStatus('Exporting...');
    setError(null);

    try {
      await downloadContent({
        content,
        format,
        filename,
        title
      });
      setIsOpen(false);
      setDownloadStatus('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Download failed');
      setDownloadStatus('');
    } finally {
      setIsDownloading(false);
    }
  };

  const getFormatIcon = (format: string) => {
    switch (format) {
      case 'xlsx':
      case 'csv':
        return <FileSpreadsheet className="w-4 h-4" />;
      case 'pdf':
      case 'docx':
        return <FileText className="w-4 h-4" />;
      default:
        return <File className="w-4 h-4" />;
    }
  };

  const getFormatColor = (format: string) => {
    switch (format) {
      case 'xlsx':
        return 'text-green-600';
      case 'csv':
        return 'text-blue-600';
      case 'pdf':
        return 'text-red-600';
      case 'docx':
        return 'text-blue-700';
      case 'txt':
        return 'text-gray-600';
      case 'md':
        return 'text-purple-600';
      case 'json':
        return 'text-orange-600';
      default:
        return 'text-gray-600';
    }
  };

  return (
    <div className={`relative inline-block ${className}`}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        disabled={isDownloading}
        className="flex items-center gap-2 px-3 py-1.5 bg-gray-100 hover:bg-gray-200 rounded-md text-sm text-gray-700 transition-colors disabled:opacity-50"
        title="Download response"
      >
        <Download className="w-4 h-4" />
        <span>{downloadStatus || 'Download'}</span>
        <ChevronDown className={`w-3 h-3 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {isOpen && (
        <div className="absolute top-full right-0 mt-1 bg-gt-white border border-gray-200 rounded-lg shadow-lg z-10 min-w-48">
          <div className="p-2 border-b border-gray-100">
            <div className="text-xs font-medium text-gray-500 mb-1">Download as:</div>
          </div>
          
          <div className="p-1">
            {suggestedFormats.map((format) => (
              <button
                key={format}
                onClick={() => handleDownload(format as DownloadOptions['format'])}
                disabled={isDownloading}
                className="w-full flex items-center gap-3 px-3 py-2 text-sm text-left hover:bg-gray-50 rounded-md transition-colors disabled:opacity-50"
              >
                <div className={getFormatColor(format)}>
                  {getFormatIcon(format)}
                </div>
                <div className="flex-1">
                  <div className="font-medium text-gray-900">{format.toUpperCase()}</div>
                  <div className="text-xs text-gray-500">{getFormatDescription(format)}</div>
                </div>
              </button>
            ))}
          </div>

          {error && (
            <div className="p-2 border-t border-gray-100">
              <div className="text-xs text-red-600">{error}</div>
            </div>
          )}
        </div>
      )}

      {/* Backdrop to close dropdown */}
      {isOpen && (
        <div 
          className="fixed inset-0 z-0" 
          onClick={() => setIsOpen(false)}
        />
      )}
    </div>
  );
}