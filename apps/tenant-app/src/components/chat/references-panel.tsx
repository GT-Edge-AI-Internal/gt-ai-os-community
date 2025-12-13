'use client';

import { useState } from 'react';
import { ChevronDown, ChevronUp, Database, MessageSquare, ExternalLink, FileText, Copy, Link } from 'lucide-react';
import { cn, formatDateOnly } from '@/lib/utils';

export interface ReferenceSource {
  id: string;
  type: 'dataset' | 'history' | 'document';
  name: string;
  relevance: number;
  content?: string;
  url?: string; // URL for document linking
  metadata?: {
    conversation_title?: string;
    agent_name?: string;
    created_at?: string;
    chunks?: number;
    file_type?: string;
    document_id?: string; // For linking to document viewer
  };
}

interface ReferencesPanelProps {
  sources: ReferenceSource[];
  isVisible: boolean;
  onToggle: () => void;
  className?: string;
}

export function ReferencesPanel({
  sources,
  isVisible,
  onToggle,
  className = ''
}: ReferencesPanelProps) {
  const [expandedSources, setExpandedSources] = useState<Set<string>>(new Set());
  const [copiedCitation, setCopiedCitation] = useState<string | null>(null);

  const toggleSource = (sourceId: string) => {
    const newExpanded = new Set(expandedSources);
    if (newExpanded.has(sourceId)) {
      newExpanded.delete(sourceId);
    } else {
      newExpanded.add(sourceId);
    }
    setExpandedSources(newExpanded);
  };

  const getSourceIcon = (type: ReferenceSource['type']) => {
    switch (type) {
      case 'dataset':
        return <Database className="w-4 h-4" />;
      case 'history':
        return <MessageSquare className="w-4 h-4" />;
      case 'document':
        return <FileText className="w-4 h-4" />;
      default:
        return <FileText className="w-4 h-4" />;
    }
  };

  const getSourceTypeColor = (type: ReferenceSource['type']) => {
    switch (type) {
      case 'dataset':
        return 'text-blue-600 bg-blue-50 border-blue-200';
      case 'history':
        return 'text-purple-600 bg-purple-50 border-purple-200';
      case 'document':
        return 'text-green-600 bg-green-50 border-green-200';
      default:
        return 'text-gray-600 bg-gray-50 border-gray-200';
    }
  };

  const formatRelevance = (relevance: number) => {
    return Math.round(relevance * 100);
  };

  const generateCitation = (source: ReferenceSource) => {
    const date = source.metadata?.created_at ?
      formatDateOnly(source.metadata.created_at) :
      formatDateOnly(new Date());

    switch (source.type) {
      case 'document':
        return `${source.name} (${source.metadata?.file_type || 'Document'}). GT 2.0 Knowledge Base. Retrieved ${date}.`;
      case 'dataset':
        return `"${source.name}" dataset. GT 2.0 Knowledge Base. Retrieved ${date}.`;
      case 'history':
        const conversation = source.metadata?.conversation_title || 'Conversation';
        const agent = source.metadata?.agent_name || 'AI Assistant';
        return `${agent}. "${conversation}." GT 2.0 Conversation History. ${date}.`;
      default:
        return `${source.name}. GT 2.0 Knowledge Base. Retrieved ${date}.`;
    }
  };

  const copyCitation = async (source: ReferenceSource) => {
    const citation = generateCitation(source);
    try {
      await navigator.clipboard.writeText(citation);
      setCopiedCitation(source.id);
      setTimeout(() => setCopiedCitation(null), 2000);
    } catch (err) {
      console.error('Failed to copy citation:', err);
    }
  };

  const openDocument = (source: ReferenceSource) => {
    // Navigate to document if it's a document type
    if (source.type === 'document') {
      if (source.url) {
        // Open external URL
        window.open(source.url, '_blank');
      } else if (source.metadata?.document_id) {
        // Navigate to internal document viewer
        const documentUrl = `/documents/${source.metadata.document_id}`;
        window.open(documentUrl, '_blank');
      } else {
        // Fallback - try to construct URL from ID
        const documentUrl = `/documents/${source.id}`;
        window.open(documentUrl, '_blank');
      }
    }
  };

  if (sources.length === 0) return null;

  return (
    <div className={cn('bg-gt-white border border-gt-gray-200 rounded-lg shadow-sm', className)}>
      {/* Header */}
      <button
        onClick={onToggle}
        className="w-full px-4 py-3 flex items-center justify-between text-left hover:bg-gt-gray-50 transition-colors rounded-t-lg"
      >
        <div className="flex items-center space-x-2">
          <ExternalLink className="w-4 h-4 text-gt-gray-500" />
          <span className="font-medium text-gt-gray-900">
            References ({sources.length})
          </span>
        </div>
        <div className="flex items-center space-x-2">
          <span className="text-sm text-gt-gray-500">
            {isVisible ? 'Hide sources' : 'Show sources'}
          </span>
          {isVisible ? (
            <ChevronUp className="w-4 h-4 text-gt-gray-400" />
          ) : (
            <ChevronDown className="w-4 h-4 text-gt-gray-400" />
          )}
        </div>
      </button>

      {/* Content */}
      {isVisible && (
        <div className="border-t border-gt-gray-200 max-h-96 overflow-y-auto">
          {sources.map((source, index) => (
            <div
              key={source.id}
              className={cn(
                'border-b border-gt-gray-100 last:border-b-0',
                expandedSources.has(source.id) ? 'bg-gt-gray-25' : ''
              )}
            >
              {/* Source Summary */}
              <button
                onClick={() => toggleSource(source.id)}
                className="w-full px-4 py-3 flex items-start justify-between text-left hover:bg-gt-gray-25 transition-colors"
              >
                <div className="flex items-start space-x-3 flex-1 min-w-0">
                  <div className={cn(
                    'p-1.5 rounded-md border flex-shrink-0 mt-0.5',
                    getSourceTypeColor(source.type)
                  )}>
                    {getSourceIcon(source.type)}
                  </div>
                  
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center space-x-2 mb-1">
                      <span className="font-medium text-gt-gray-900 truncate">
                        {source.name}
                      </span>
                      <span className="text-xs font-mono text-gt-gray-500 bg-gt-gray-100 px-2 py-0.5 rounded-full">
                        {formatRelevance(source.relevance)}%
                      </span>
                    </div>
                    
                    <div className="flex items-center space-x-2 text-xs text-gt-gray-500">
                      <span className="capitalize">{source.type}</span>
                      {source.metadata?.conversation_title && (
                        <>
                          <span>•</span>
                          <span className="truncate max-w-32">
                            {source.metadata.conversation_title}
                          </span>
                        </>
                      )}
                      {source.metadata?.agent_name && (
                        <>
                          <span>•</span>
                          <span>{source.metadata.agent_name}</span>
                        </>
                      )}
                      {source.metadata?.chunks && (
                        <>
                          <span>•</span>
                          <span>{source.metadata.chunks} chunks</span>
                        </>
                      )}
                    </div>
                  </div>
                </div>
                
                <ChevronDown
                  className={cn(
                    'w-4 h-4 text-gt-gray-400 transition-transform flex-shrink-0 mt-1',
                    expandedSources.has(source.id) ? 'transform rotate-180' : ''
                  )}
                />
              </button>

              {/* Expanded Content */}
              {expandedSources.has(source.id) && source.content && (
                <div className="px-4 pb-3">
                  <div className="bg-gt-gray-50 rounded-md p-3 text-sm text-gt-gray-700 border-l-4 border-gt-blue-200">
                    <div className="whitespace-pre-wrap line-clamp-6">
                      {source.content.length > 500 
                        ? `${source.content.substring(0, 500)}...` 
                        : source.content}
                    </div>
                    
                    {/* Citation and Actions */}
                    <div className="mt-3 pt-3 border-t border-gt-gray-200 space-y-2">
                      <div className="text-xs text-gt-gray-500">
                        <strong>Citation:</strong> {generateCitation(source)}
                      </div>

                      <div className="flex items-center justify-between">
                        <div className="text-xs text-gt-gray-500">
                          {source.metadata?.created_at && (
                            <span>Created: {formatDateOnly(source.metadata.created_at)}</span>
                          )}
                        </div>

                        <div className="flex items-center space-x-1">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              copyCitation(source);
                            }}
                            className={cn(
                              'flex items-center space-x-1 px-2 py-1 text-xs rounded transition-colors',
                              copiedCitation === source.id
                                ? 'text-green-600 bg-green-50'
                                : 'text-gt-gray-600 hover:text-gt-gray-800 hover:bg-gt-gray-100'
                            )}
                            title="Copy citation"
                          >
                            <Copy className="w-3 h-3" />
                            <span>{copiedCitation === source.id ? 'Copied!' : 'Cite'}</span>
                          </button>

                          {source.type === 'document' && (
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                openDocument(source);
                              }}
                              className="flex items-center space-x-1 px-2 py-1 text-xs text-gt-gray-600 hover:text-gt-gray-800 hover:bg-gt-gray-100 rounded transition-colors"
                              title="Open document"
                            >
                              <Link className="w-3 h-3" />
                              <span>Open</span>
                            </button>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          ))}
          
          {/* Footer */}
          <div className="px-4 py-2 bg-gt-gray-25 text-xs text-gt-gray-500 text-center">
            Sources ranked by relevance • Click to expand content
          </div>
        </div>
      )}
    </div>
  );
}