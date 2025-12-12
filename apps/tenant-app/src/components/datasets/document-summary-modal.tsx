'use client';

import { useState, useEffect } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog';
import { Badge } from '@/components/ui/badge';
// import { ScrollArea } from '@/components/ui/scroll-area';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import {
  FileText,
  Hash,
  Calendar,
  Database,
  FileSearch,
  Info,
  Copy,
  X
} from 'lucide-react';
import { documentService } from '@/services';
import { cn, formatDateTime, formatFileSize } from '@/lib/utils';

interface DocumentSummaryModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  documentId: string;
}

interface DocumentDetails {
  id: string;
  filename: string;
  original_filename: string;
  file_type: string;
  file_size_bytes: number;
  processing_status: string;
  chunk_count?: number;
  created_at: string;
  processed_at?: string;
  content_summary?: string;
  key_topics?: string[];
  metadata?: Record<string, any>;
  dataset_id?: string;
  dataset_name?: string;
}

export function DocumentSummaryModal({
  open,
  onOpenChange,
  documentId
}: DocumentSummaryModalProps) {
  const [loading, setLoading] = useState(false);
  const [document, setDocument] = useState<DocumentDetails | null>(null);
  const [summaryText, setSummaryText] = useState('');
  const [keyTopics, setKeyTopics] = useState<string[]>([]);
  const [activeTab, setActiveTab] = useState('summary');
  const [copiedToClipboard, setCopiedToClipboard] = useState(false);

  useEffect(() => {
    if (open && documentId) {
      loadDocumentDetails();
    }
  }, [open, documentId]);

  const loadDocumentDetails = async () => {
    setLoading(true);
    try {
      // Get document details
      const response = await documentService.getDocument(documentId);

      if (response.data) {
        setDocument(response.data);

        // If we have a summary, parse it
        if (response.data.content_summary) {
          setSummaryText(response.data.content_summary);
        } else {
          // Generate a summary if not available
          await generateSummary();
        }

        // Extract key topics if available
        if (response.data.key_topics) {
          setKeyTopics(response.data.key_topics);
        }
      }
    } catch (error) {
      console.error('Failed to load document details:', error);
    } finally {
      setLoading(false);
    }
  };

  const generateSummary = async () => {
    try {
      const response = await documentService.generateSummary(documentId);
      if (response.data) {
        setSummaryText(response.data.summary);
        setKeyTopics(response.data.key_topics || []);
      }
    } catch (error) {
      console.error('Failed to generate summary:', error);
      setSummaryText('Summary generation failed. Please try again later.');
    }
  };


  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedToClipboard(true);
    setTimeout(() => setCopiedToClipboard(false), 2000);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl max-h-[80vh]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <FileSearch className="w-5 h-5 text-gt-green" />
            Document Summary
          </DialogTitle>
          {document && (
            <DialogDescription>
              {document.original_filename}
            </DialogDescription>
          )}
        </DialogHeader>

        {loading ? (
          <div className="space-y-4 py-6">
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-5/6" />
            <Skeleton className="h-20 w-full" />
          </div>
        ) : document ? (
          <Tabs value={activeTab} onValueChange={setActiveTab} className="mt-4">
            <TabsList className="grid w-full grid-cols-3">
              <TabsTrigger value="summary">Summary</TabsTrigger>
              <TabsTrigger value="details">Details</TabsTrigger>
              <TabsTrigger value="metadata">Metadata</TabsTrigger>
            </TabsList>

            <TabsContent value="summary" className="space-y-4 mt-4">
              <div className="h-[400px] w-full rounded-lg border p-4 overflow-y-auto">
                {/* Key Topics */}
                {keyTopics.length > 0 && (
                  <div className="mb-4">
                    <h3 className="text-sm font-semibold text-gray-700 mb-2">Key Topics</h3>
                    <div className="flex flex-wrap gap-2">
                      {keyTopics.map((topic, index) => (
                        <Badge key={index} variant="secondary">
                          {topic}
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}

                {/* Summary Text */}
                <div>
                  <h3 className="text-sm font-semibold text-gray-700 mb-2">Content Summary</h3>
                  <div className="prose prose-sm max-w-none">
                    <p className="text-gray-600 whitespace-pre-wrap">
                      {summaryText || 'No summary available for this document.'}
                    </p>
                  </div>
                </div>

                {/* Copy Summary Button */}
                {summaryText && (
                  <Button
                    variant="outline"
                    size="sm"
                    className="mt-4"
                    onClick={() => copyToClipboard(summaryText)}
                  >
                    <Copy className="w-4 h-4 mr-2" />
                    {copiedToClipboard ? 'Copied!' : 'Copy Summary'}
                  </Button>
                )}
              </div>
            </TabsContent>

            <TabsContent value="details" className="space-y-4 mt-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-3">
                  <div>
                    <p className="text-sm font-medium text-gray-500">File Type</p>
                    <p className="text-sm text-gray-900">{document.file_type.toUpperCase()}</p>
                  </div>
                  <div>
                    <p className="text-sm font-medium text-gray-500">File Size</p>
                    <p className="text-sm text-gray-900">{formatFileSize(document.file_size_bytes)}</p>
                  </div>
                  <div>
                    <p className="text-sm font-medium text-gray-500">Processing Status</p>
                    <Badge className={cn(
                      'text-xs',
                      document.processing_status === 'completed' ? 'bg-green-100 text-green-800' :
                      document.processing_status === 'processing' ? 'bg-blue-100 text-blue-800' :
                      document.processing_status === 'failed' ? 'bg-red-100 text-red-800' :
                      'bg-gray-100 text-gray-800'
                    )}>
                      {document.processing_status}
                    </Badge>
                  </div>
                </div>

                <div className="space-y-3">
                  <div>
                    <p className="text-sm font-medium text-gray-500">Chunks</p>
                    <p className="text-sm text-gray-900">{document.chunk_count || 0} chunks</p>
                  </div>
                  <div>
                    <p className="text-sm font-medium text-gray-500">Created</p>
                    <p className="text-sm text-gray-900">
                      {formatDateTime(document.created_at)}
                    </p>
                  </div>
                  {document.processed_at && (
                    <div>
                      <p className="text-sm font-medium text-gray-500">Processed</p>
                      <p className="text-sm text-gray-900">
                        {formatDateTime(document.processed_at)}
                      </p>
                    </div>
                  )}
                </div>
              </div>

              {document.dataset_name && (
                <div className="mt-4 p-4 bg-gray-50 rounded-lg">
                  <div className="flex items-center gap-2 text-sm">
                    <Database className="w-4 h-4 text-gray-500" />
                    <span className="text-gray-600">Dataset:</span>
                    <span className="font-medium text-gray-900">{document.dataset_name}</span>
                  </div>
                </div>
              )}

              <div className="mt-4 p-4 bg-blue-50 rounded-lg">
                <div className="flex items-start gap-2">
                  <Info className="w-4 h-4 text-blue-600 mt-0.5" />
                  <div className="text-sm text-blue-800">
                    <p className="font-medium mb-1">Document ID</p>
                    <code className="text-xs bg-blue-100 px-2 py-1 rounded">
                      {document.id}
                    </code>
                  </div>
                </div>
              </div>
            </TabsContent>

            <TabsContent value="metadata" className="mt-4">
              <div className="h-[400px] w-full rounded-lg border p-4 overflow-y-auto">
                {document.metadata && Object.keys(document.metadata).length > 0 ? (
                  <div className="space-y-2">
                    {Object.entries(document.metadata).map(([key, value]) => (
                      <div key={key} className="flex flex-col space-y-1">
                        <p className="text-sm font-medium text-gray-500">{key}</p>
                        <p className="text-sm text-gray-900 break-words">
                          {typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value)}
                        </p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-gray-500">No metadata available for this document.</p>
                )}
              </div>
            </TabsContent>
          </Tabs>
        ) : (
          <div className="py-8 text-center">
            <FileText className="w-12 h-12 text-gray-400 mx-auto mb-4" />
            <p className="text-gray-600">Failed to load document details.</p>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}