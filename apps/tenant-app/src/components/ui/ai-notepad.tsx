'use client';

import { useState, useRef } from 'react';
import { Copy, Check, Maximize2, Minimize2, Download, Eye, Code } from 'lucide-react';
import { MermaidChart } from './mermaid-chart';
import { copyToClipboard } from '@/lib/utils';

interface AINotePadContent {
  type: 'code' | 'mermaid' | 'text' | 'json' | 'html' | 'markdown';
  content: string;
  language?: string;
  title?: string;
}

interface AINotePadProps {
  contents: AINotePadContent[];
  title?: string;
  className?: string;
}

export function AINotepad({ contents, title = "AI Notepad", className = '' }: AINotePadProps) {
  const [activeTab, setActiveTab] = useState(0);
  const [isExpanded, setIsExpanded] = useState(false);
  const [copied, setCopied] = useState<number | null>(null);
  const [viewMode, setViewMode] = useState<'preview' | 'code'>('preview');

  const handleCopy = async (content: string, index: number) => {
    const success = await copyToClipboard(content);
    if (success) {
      setCopied(index);
      setTimeout(() => setCopied(null), 2000);
    }
  };

  const handleDownload = (content: string, filename: string) => {
    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  };

  const getFileExtension = (type: string, language?: string) => {
    if (language) return language;
    switch (type) {
      case 'mermaid': return 'mmd';
      case 'json': return 'json';
      case 'html': return 'html';
      case 'markdown': return 'md';
      case 'code': return 'txt';
      default: return 'txt';
    }
  };

  const renderContent = (content: AINotePadContent, index: number) => {
    const shouldShowPreview = viewMode === 'preview' && (content.type === 'mermaid' || content.type === 'html');

    if (shouldShowPreview) {
      switch (content.type) {
        case 'mermaid':
          return (
            <div className="w-full h-full overflow-hidden">
              <MermaidChart className={`w-full ${isExpanded ? 'h-full' : ''}`}>
                {content.content}
              </MermaidChart>
            </div>
          );
        case 'html':
          return (
            <div 
              className="w-full h-full overflow-auto p-4 bg-white rounded"
              dangerouslySetInnerHTML={{ __html: content.content }}
            />
          );
        default:
          return null;
      }
    }

    // Code view for all content types
    return (
      <div className="w-full h-full overflow-auto">
        <pre className="text-sm font-mono text-gray-300 whitespace-pre-wrap break-words p-4">
          <code>{content.content}</code>
        </pre>
      </div>
    );
  };

  const currentContent = contents[activeTab];
  const canToggleView = currentContent?.type === 'mermaid' || currentContent?.type === 'html';

  return (
    <div className={`ai-notepad bg-gray-900 border border-gray-700 rounded-lg overflow-hidden ${
      isExpanded ? 'fixed inset-4 z-50 flex flex-col' : 'w-full max-w-2xl'
    } ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between p-3 bg-gray-800 border-b border-gray-700">
        <div className="flex items-center space-x-2">
          <span className="text-sm font-medium text-gray-300">{title}</span>
        </div>
        
        <div className="flex items-center space-x-2">
          {canToggleView && (
            <button
              onClick={() => setViewMode(viewMode === 'preview' ? 'code' : 'preview')}
              className="p-1.5 text-gray-400 hover:text-white hover:bg-gray-700 rounded transition-colors"
              title={viewMode === 'preview' ? 'Show code' : 'Show preview'}
            >
              {viewMode === 'preview' ? <Code className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            </button>
          )}
          
          <button
            onClick={() => handleCopy(currentContent?.content || '', activeTab)}
            className="p-1.5 text-gray-400 hover:text-white hover:bg-gray-700 rounded transition-colors"
            title="Copy content"
          >
            {copied === activeTab ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
          </button>
          
          <button
            onClick={() => handleDownload(
              currentContent?.content || '', 
              `notepad-${activeTab + 1}.${getFileExtension(currentContent?.type || 'text', currentContent?.language)}`
            )}
            className="p-1.5 text-gray-400 hover:text-white hover:bg-gray-700 rounded transition-colors"
            title="Download"
          >
            <Download className="w-4 h-4" />
          </button>
          
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="p-1.5 text-gray-400 hover:text-white hover:bg-gray-700 rounded transition-colors"
            title={isExpanded ? 'Minimize' : 'Expand'}
          >
            {isExpanded ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {/* Tabs */}
      {contents.length > 1 && (
        <div className="flex bg-gray-800 border-b border-gray-700 overflow-x-auto">
          {contents.map((content, index) => (
            <button
              key={index}
              onClick={() => setActiveTab(index)}
              className={`px-4 py-2 text-sm font-medium border-b-2 whitespace-nowrap transition-colors ${
                activeTab === index
                  ? 'text-blue-400 border-blue-400'
                  : 'text-gray-400 border-transparent hover:text-gray-300'
              }`}
            >
              {content.title || `${content.type}${content.language ? ` (${content.language})` : ''}`}
            </button>
          ))}
        </div>
      )}

      {/* Content */}
      <div className={`bg-gray-900 ${isExpanded ? 'flex-1' : 'h-96'}`}>
        {currentContent && renderContent(currentContent, activeTab)}
      </div>

      {/* Status Bar */}
      <div className="flex items-center justify-between px-3 py-2 bg-gray-800 border-t border-gray-700 text-xs text-gray-400">
        <span>
          {currentContent?.type === 'mermaid' ? 'Mermaid Diagram' : 
           currentContent?.language ? `${currentContent.language.toUpperCase()}` : 
           currentContent?.type?.toUpperCase() || 'TEXT'}
        </span>
        <span>
          {currentContent?.content.split('\n').length || 0} lines, {currentContent?.content.length || 0} chars
        </span>
      </div>
    </div>
  );
}