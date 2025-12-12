'use client';

import { useState, useEffect, useMemo } from 'react';
import { 
  Search,
  Filter,
  ZoomIn,
  ZoomOut,
  RotateCcw,
  Settings,
  Eye,
  EyeOff,
  Play,
  Pause,
  BarChart3,
  Network,
  FileText,
  Layers,
  Target,
  Download,
  RefreshCw
} from 'lucide-react';
import { cn, formatTime } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Slider } from '@/components/ui/slider';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import { Separator } from '@/components/ui/separator';

interface RAGDocument {
  id: string;
  name: string;
  type: string;
  chunks: number;
  vectors: number;
  similarity?: number;
  embedding?: number[];
  status: 'completed' | 'processing' | 'failed';
}

interface Chunk {
  id: string;
  documentId: string;
  content: string;
  index: number;
  tokens: number;
  embedding: number[];
  similarity?: number;
}

interface QueryResult {
  query: string;
  results: Array<{
    documentId: string;
    chunkId: string;
    similarity: number;
    content: string;
  }>;
  method: 'vector' | 'hybrid' | 'keyword';
  timestamp: Date;
}

interface RAGVisualizationProps {
  documents: RAGDocument[];
  onDocumentSelect?: (documentId: string) => void;
  onQueryTest?: (query: string, method: string) => Promise<QueryResult>;
  className?: string;
}

export function RAGVisualization({
  documents,
  onDocumentSelect,
  onQueryTest,
  className = ''
}: RAGVisualizationProps) {
  const [viewMode, setViewMode] = useState<'graph' | 'grid' | 'analysis'>('graph');
  const [queryText, setQueryText] = useState('');
  const [searchMethod, setSearchMethod] = useState<'vector' | 'hybrid' | 'keyword'>('hybrid');
  const [queryResults, setQueryResults] = useState<QueryResult[]>([]);
  const [isQuerying, setIsQuerying] = useState(false);
  const [selectedDocument, setSelectedDocument] = useState<string | null>(null);
  const [zoomLevel, setZoomLevel] = useState(100);
  const [showChunks, setShowChunks] = useState(true);
  const [showSimilarity, setShowSimilarity] = useState(false);
  const [similarityThreshold, setSimilarityThreshold] = useState([0.7]);
  const [isPlaying, setIsPlaying] = useState(false);
  const [highlightedNodes, setHighlightedNodes] = useState<Set<string>>(new Set());

  // Mock chunk data for visualization
  const mockChunks = useMemo(() => {
    const chunks: Chunk[] = [];
    documents.forEach(doc => {
      for (let i = 0; i < doc.chunks; i++) {
        chunks.push({
          id: `${doc.id}-chunk-${i}`,
          documentId: doc.id,
          content: `Chunk ${i + 1} content from ${doc.name}`,
          index: i,
          tokens: Math.floor(Math.random() * 500) + 100,
          embedding: Array.from({ length: 1024 }, () => Math.random() - 0.5),
          similarity: Math.random()
        });
      }
    });
    return chunks;
  }, [documents]);

  // Calculate document similarities
  const documentSimilarities = useMemo(() => {
    const similarities: Array<{ doc1: string; doc2: string; similarity: number }> = [];
    for (let i = 0; i < documents.length; i++) {
      for (let j = i + 1; j < documents.length; j++) {
        similarities.push({
          doc1: documents[i].id,
          doc2: documents[j].id,
          similarity: Math.random() * 0.6 + 0.2 // 0.2 to 0.8 range
        });
      }
    }
    return similarities.filter(s => s.similarity >= similarityThreshold[0]);
  }, [documents, similarityThreshold]);

  const handleQueryTest = async () => {
    if (!queryText.trim()) return;

    setIsQuerying(true);
    try {
      // Call real search API
      const response = await fetch('/api/v1/search', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
        },
        body: JSON.stringify({
          query: queryText,
          search_type: searchMethod,
          max_results: 10,
          min_similarity: similarityThreshold[0]
        })
      });

      if (!response.ok) {
        throw new Error(`Search failed: ${response.statusText}`);
      }

      const searchData = await response.json();

      // Transform API response to expected format
      const result: QueryResult = {
        query: queryText,
        method: searchMethod,
        timestamp: new Date(),
        results: searchData.results.map((r: any) => ({
          documentId: r.document_id,
          chunkId: r.chunk_id,
          similarity: r.vector_similarity,
          content: r.text
        }))
      };

      setQueryResults(prev => [result, ...prev.slice(0, 4)]);

      // Highlight relevant documents
      const relevantDocs = new Set(result.results.map(r => r.documentId));
      setHighlightedNodes(relevantDocs);

      // Auto-hide highlights after 5 seconds
      setTimeout(() => setHighlightedNodes(new Set()), 5000);

      // Call onQueryTest callback if provided
      if (onQueryTest) {
        await onQueryTest(queryText, searchMethod);
      }
    } catch (error) {
      console.error('Query test failed:', error);
    } finally {
      setIsQuerying(false);
    }
  };

  const handleDocumentClick = (documentId: string) => {
    setSelectedDocument(selectedDocument === documentId ? null : documentId);
    onDocumentSelect?.(documentId);
  };

  const resetView = () => {
    setZoomLevel(100);
    setSelectedDocument(null);
    setHighlightedNodes(new Set());
    setQueryResults([]);
  };

  const exportVisualization = () => {
    // Mock export functionality
    console.log('Exporting visualization data...');
    const exportData = {
      documents,
      chunks: mockChunks,
      similarities: documentSimilarities,
      queries: queryResults,
      timestamp: new Date().toISOString()
    };
    
    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `rag-visualization-${Date.now()}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div className={cn('space-y-6', className)}>
      {/* Controls Panel */}
      <Card className="p-4">
        <div className="flex flex-wrap items-center gap-4">
          {/* View Mode */}
          <div className="flex items-center gap-2">
            <Label className="text-sm font-medium">View:</Label>
            <div className="flex bg-gray-100 rounded-lg p-1">
              {[
                { id: 'graph', icon: Network, label: 'Graph' },
                { id: 'grid', icon: Layers, label: 'Grid' },
                { id: 'analysis', icon: BarChart3, label: 'Analysis' }
              ].map(({ id, icon: Icon, label }) => (
                <Button
                  key={id}
                  variant={viewMode === id ? 'default' : 'ghost'}
                  size="sm"
                  onClick={() => setViewMode(id as any)}
                  className="px-3 py-1 text-xs"
                >
                  <Icon className="w-3 h-3 mr-1" />
                  {label}
                </Button>
              ))}
            </div>
          </div>

          <Separator orientation="vertical" className="h-6" />

          {/* Query Test */}
          <div className="flex items-center gap-2 flex-1 max-w-md">
            <Input
              placeholder="Test RAG query..."
              value={queryText}
              onChange={(e) => setQueryText(e.target?.value || '')}
              onKeyPress={(e) => e.key === 'Enter' && handleQueryTest()}
              className="text-sm"
            />
            <Select value={searchMethod} onValueChange={(value: any) => setSearchMethod(value)}>
              <SelectTrigger className="w-24">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="vector">Vector</SelectItem>
                <SelectItem value="hybrid">Hybrid</SelectItem>
                <SelectItem value="keyword">Keyword</SelectItem>
              </SelectContent>
            </Select>
            <Button 
              onClick={handleQueryTest}
              disabled={!queryText.trim() || isQuerying}
              size="sm"
            >
              {isQuerying ? (
                <RefreshCw className="w-4 h-4 animate-spin" />
              ) : (
                <Search className="w-4 h-4" />
              )}
            </Button>
          </div>

          <Separator orientation="vertical" className="h-6" />

          {/* View Controls */}
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setZoomLevel(Math.min(200, zoomLevel + 25))}
            >
              <ZoomIn className="w-4 h-4" />
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setZoomLevel(Math.max(50, zoomLevel - 25))}
            >
              <ZoomOut className="w-4 h-4" />
            </Button>
            <Button variant="outline" size="sm" onClick={resetView}>
              <RotateCcw className="w-4 h-4" />
            </Button>
            <Button variant="outline" size="sm" onClick={exportVisualization}>
              <Download className="w-4 h-4" />
            </Button>
          </div>
        </div>

        {/* Advanced Controls */}
        <div className="mt-4 pt-4 border-t flex flex-wrap items-center gap-4">
          <div className="flex items-center space-x-2">
            <Checkbox
              id="show-chunks"
              checked={showChunks}
              onCheckedChange={setShowChunks}
            />
            <Label htmlFor="show-chunks" className="text-sm">Show chunks</Label>
          </div>

          <div className="flex items-center space-x-2">
            <Checkbox
              id="show-similarity"
              checked={showSimilarity}
              onCheckedChange={setShowSimilarity}
            />
            <Label htmlFor="show-similarity" className="text-sm">Show similarity</Label>
          </div>

          <div className="flex items-center gap-2">
            <Label className="text-sm">Similarity threshold:</Label>
            <div className="w-32">
              <Slider
                value={similarityThreshold}
                onValueChange={setSimilarityThreshold}
                max={1}
                min={0}
                step={0.1}
                className="w-full"
              />
            </div>
            <span className="text-xs text-gray-500 w-8">
              {similarityThreshold[0].toFixed(1)}
            </span>
          </div>
        </div>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Main Visualization Area */}
        <div className="lg:col-span-3">
          <Card className="p-6">
            {viewMode === 'graph' && (
              <GraphView
                documents={documents}
                chunks={showChunks ? mockChunks : []}
                similarities={showSimilarity ? documentSimilarities : []}
                selectedDocument={selectedDocument}
                highlightedNodes={highlightedNodes}
                zoomLevel={zoomLevel}
                onDocumentClick={handleDocumentClick}
              />
            )}

            {viewMode === 'grid' && (
              <GridView
                documents={documents}
                chunks={mockChunks}
                selectedDocument={selectedDocument}
                onDocumentClick={handleDocumentClick}
              />
            )}

            {viewMode === 'analysis' && (
              <AnalysisView
                documents={documents}
                chunks={mockChunks}
                similarities={documentSimilarities}
                queryResults={queryResults}
              />
            )}
          </Card>
        </div>

        {/* Side Panel */}
        <div className="space-y-6">
          {/* Query Results */}
          {queryResults.length > 0 && (
            <Card className="p-4">
              <h3 className="font-semibold text-sm mb-3 flex items-center gap-2">
                <Target className="w-4 h-4" />
                Query Results
              </h3>
              <div className="space-y-3">
                {queryResults.map((result, index) => (
                  <div key={index} className="border rounded p-3">
                    <div className="flex items-center justify-between mb-2">
                      <Badge variant="outline" className="text-xs">
                        {result.method}
                      </Badge>
                      <span className="text-xs text-gray-500">
                        {formatTime(result.timestamp)}
                      </span>
                    </div>
                    <p className="text-sm font-medium mb-1">{result.query}</p>
                    <p className="text-xs text-gray-600">
                      {result.results.length} results found
                    </p>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* Document Details */}
          {selectedDocument && (
            <Card className="p-4">
              <h3 className="font-semibold text-sm mb-3 flex items-center gap-2">
                <FileText className="w-4 h-4" />
                Document Details
              </h3>
              {(() => {
                const doc = documents.find(d => d.id === selectedDocument);
                if (!doc) return null;
                
                const docChunks = mockChunks.filter(c => c.documentId === selectedDocument);
                
                return (
                  <div className="space-y-3">
                    <div>
                      <p className="font-medium text-sm">{doc.name}</p>
                      <p className="text-xs text-gray-600 uppercase">{doc.type}</p>
                    </div>
                    
                    <div className="grid grid-cols-2 gap-2 text-xs">
                      <div>
                        <p className="text-gray-500">Chunks</p>
                        <p className="font-medium">{doc.chunks.toLocaleString()}</p>
                      </div>
                      <div>
                        <p className="text-gray-500">Vectors</p>
                        <p className="font-medium">{doc.vectors.toLocaleString()}</p>
                      </div>
                    </div>
                    
                    <Separator />
                    
                    <div>
                      <p className="text-xs text-gray-500 mb-2">Recent Chunks</p>
                      <div className="space-y-2">
                        {docChunks.slice(0, 3).map(chunk => (
                          <div key={chunk.id} className="p-2 bg-gray-50 rounded text-xs">
                            <p className="font-medium">Chunk {chunk.index + 1}</p>
                            <p className="text-gray-600 line-clamp-2">{chunk.content}</p>
                            <p className="text-gray-500 mt-1">{chunk.tokens} tokens</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                );
              })()}
            </Card>
          )}

          {/* Statistics */}
          <Card className="p-4">
            <h3 className="font-semibold text-sm mb-3 flex items-center gap-2">
              <BarChart3 className="w-4 h-4" />
              Statistics
            </h3>
            <div className="space-y-3 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-600">Total Documents</span>
                <span className="font-medium">{documents.length}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Total Chunks</span>
                <span className="font-medium">
                  {documents.reduce((sum, doc) => sum + doc.chunks, 0).toLocaleString()}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Total Vectors</span>
                <span className="font-medium">
                  {documents.reduce((sum, doc) => sum + doc.vectors, 0).toLocaleString()}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Avg Similarity</span>
                <span className="font-medium">
                  {documentSimilarities.length > 0 
                    ? (documentSimilarities.reduce((sum, s) => sum + s.similarity, 0) / documentSimilarities.length).toFixed(2)
                    : 'N/A'
                  }
                </span>
              </div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}

// Graph View Component
function GraphView({ 
  documents, 
  chunks, 
  similarities, 
  selectedDocument, 
  highlightedNodes,
  zoomLevel,
  onDocumentClick 
}: {
  documents: RAGDocument[];
  chunks: Chunk[];
  similarities: Array<{ doc1: string; doc2: string; similarity: number }>;
  selectedDocument: string | null;
  highlightedNodes: Set<string>;
  zoomLevel: number;
  onDocumentClick: (id: string) => void;
}) {
  return (
    <div 
      className="relative bg-gray-50 rounded border min-h-[500px] overflow-hidden"
      style={{ transform: `scale(${zoomLevel / 100})` }}
    >
      {/* SVG Graph Visualization */}
      <svg width="100%" height="500" className="absolute inset-0">
        {/* Similarity Lines */}
        {similarities.map((sim, index) => {
          const doc1Index = documents.findIndex(d => d.id === sim.doc1);
          const doc2Index = documents.findIndex(d => d.id === sim.doc2);
          if (doc1Index === -1 || doc2Index === -1) return null;
          
          const x1 = (doc1Index + 1) * (800 / (documents.length + 1));
          const y1 = 250 + Math.sin(doc1Index * 0.5) * 100;
          const x2 = (doc2Index + 1) * (800 / (documents.length + 1));
          const y2 = 250 + Math.sin(doc2Index * 0.5) * 100;
          
          return (
            <line
              key={index}
              x1={x1}
              y1={y1}
              x2={x2}
              y2={y2}
              stroke="#e5e7eb"
              strokeWidth={sim.similarity * 3}
              opacity={0.6}
            />
          );
        })}

        {/* Document Nodes */}
        {documents.map((doc, index) => {
          const x = (index + 1) * (800 / (documents.length + 1));
          const y = 250 + Math.sin(index * 0.5) * 100;
          const isSelected = selectedDocument === doc.id;
          const isHighlighted = highlightedNodes.has(doc.id);
          
          return (
            <g key={doc.id}>
              <circle
                cx={x}
                cy={y}
                r={isSelected ? 25 : 20}
                fill={isHighlighted ? '#10b981' : isSelected ? '#3b82f6' : '#6b7280'}
                stroke={isSelected ? '#1d4ed8' : '#374151'}
                strokeWidth={isSelected ? 3 : 1}
                className="cursor-pointer transition-all duration-200"
                onClick={() => onDocumentClick(doc.id)}
              />
              <text
                x={x}
                y={y + 35}
                textAnchor="middle"
                className="text-xs font-medium fill-gray-700"
                onClick={() => onDocumentClick(doc.id)}
              >
                {doc.name.length > 12 ? `${doc.name.substring(0, 12)}...` : doc.name}
              </text>
              {/* Chunk indicators */}
              {chunks.filter(c => c.documentId === doc.id).slice(0, 3).map((chunk, chunkIndex) => (
                <circle
                  key={chunk.id}
                  cx={x + (chunkIndex - 1) * 15}
                  cy={y - 35}
                  r={3}
                  fill="#f59e0b"
                  opacity={0.7}
                />
              ))}
            </g>
          );
        })}
      </svg>
      
      {/* Loading/Empty State */}
      {documents.length === 0 && (
        <div className="flex items-center justify-center h-full">
          <div className="text-center text-gray-500">
            <Network className="w-12 h-12 mx-auto mb-2 opacity-50" />
            <p>No documents to visualize</p>
          </div>
        </div>
      )}
    </div>
  );
}

// Grid View Component
function GridView({ 
  documents, 
  chunks, 
  selectedDocument, 
  onDocumentClick 
}: {
  documents: RAGDocument[];
  chunks: Chunk[];
  selectedDocument: string | null;
  onDocumentClick: (id: string) => void;
}) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
      {documents.map(doc => {
        const docChunks = chunks.filter(c => c.documentId === doc.id);
        const isSelected = selectedDocument === doc.id;
        
        return (
          <div
            key={doc.id}
            onClick={() => onDocumentClick(doc.id)}
            className={cn(
              'border rounded-lg p-4 cursor-pointer transition-all duration-200',
              isSelected ? 'border-blue-500 bg-blue-50' : 'border-gray-200 hover:border-gray-300'
            )}
          >
            <div className="flex items-center gap-2 mb-2">
              <FileText className="w-4 h-4 text-gray-500" />
              <p className="font-medium text-sm truncate">{doc.name}</p>
            </div>
            
            <div className="text-xs text-gray-600 space-y-1">
              <p>{doc.chunks} chunks • {doc.vectors} vectors</p>
              <p className="uppercase font-medium">{doc.type}</p>
            </div>
            
            {/* Mini chunk visualization */}
            <div className="mt-3 flex gap-1">
              {docChunks.slice(0, 8).map((chunk, index) => (
                <div
                  key={index}
                  className="w-2 h-8 bg-gradient-to-t from-blue-200 to-blue-400 rounded-sm"
                  style={{ 
                    height: `${Math.max(8, (chunk.tokens / 500) * 32)}px`,
                    opacity: chunk.similarity ? 0.4 + (chunk.similarity * 0.6) : 0.7
                  }}
                />
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// Analysis View Component
function AnalysisView({ 
  documents, 
  chunks, 
  similarities, 
  queryResults 
}: {
  documents: RAGDocument[];
  chunks: Chunk[];
  similarities: Array<{ doc1: string; doc2: string; similarity: number }>;
  queryResults: QueryResult[];
}) {
  const avgChunksPerDoc = documents.length > 0 ? 
    documents.reduce((sum, doc) => sum + doc.chunks, 0) / documents.length : 0;
  
  const avgVectorsPerDoc = documents.length > 0 ? 
    documents.reduce((sum, doc) => sum + doc.vectors, 0) / documents.length : 0;

  return (
    <div className="space-y-6">
      {/* Metrics Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: 'Documents', value: documents.length, change: '+12%' },
          { label: 'Total Chunks', value: documents.reduce((sum, doc) => sum + doc.chunks, 0), change: '+8%' },
          { label: 'Avg Chunks/Doc', value: Math.round(avgChunksPerDoc), change: '-2%' },
          { label: 'Query Tests', value: queryResults.length, change: 'New' }
        ].map((metric, index) => (
          <Card key={index} className="p-4">
            <div className="text-2xl font-bold text-gray-900">{metric.value.toLocaleString()}</div>
            <div className="text-sm text-gray-600">{metric.label}</div>
            <div className={cn(
              'text-xs font-medium',
              metric.change.includes('+') ? 'text-green-600' : 
              metric.change.includes('-') ? 'text-red-600' : 'text-blue-600'
            )}>
              {metric.change}
            </div>
          </Card>
        ))}
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Document Distribution */}
        <Card className="p-4">
          <h4 className="font-semibold mb-4">Document Types</h4>
          <div className="space-y-3">
            {(() => {
              const typeCount = documents.reduce((acc, doc) => {
                acc[doc.type] = (acc[doc.type] || 0) + 1;
                return acc;
              }, {} as Record<string, number>);
              
              const totalDocs = documents.length;
              
              return Object.entries(typeCount).map(([type, count]) => (
                <div key={type} className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div className="w-3 h-3 rounded-full bg-blue-500" />
                    <span className="text-sm uppercase font-medium">{type}</span>
                  </div>
                  <div className="text-sm text-gray-600">
                    {count} ({totalDocs > 0 ? Math.round((count / totalDocs) * 100) : 0}%)
                  </div>
                </div>
              ));
            })()}
          </div>
        </Card>

        {/* Similarity Distribution */}
        <Card className="p-4">
          <h4 className="font-semibold mb-4">Similarity Analysis</h4>
          <div className="space-y-3">
            {similarities.slice(0, 5).map((sim, index) => {
              const doc1 = documents.find(d => d.id === sim.doc1);
              const doc2 = documents.find(d => d.id === sim.doc2);
              
              return (
                <div key={index} className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span className="truncate">
                      {doc1?.name} ↔ {doc2?.name}
                    </span>
                    <span className="font-medium">{sim.similarity.toFixed(2)}</span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div 
                      className="bg-green-500 h-2 rounded-full transition-all duration-300"
                      style={{ width: `${sim.similarity * 100}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </Card>
      </div>

      {/* Query Performance */}
      {queryResults.length > 0 && (
        <Card className="p-4">
          <h4 className="font-semibold mb-4">Query Performance</h4>
          <div className="space-y-3">
            {queryResults.map((result, index) => (
              <div key={index} className="flex items-center justify-between p-3 bg-gray-50 rounded">
                <div className="flex-1">
                  <p className="font-medium text-sm">{result.query}</p>
                  <p className="text-xs text-gray-600">
                    {result.results.length} results • {result.method} search
                  </p>
                </div>
                <div className="text-right">
                  <Badge variant="outline">{result.method}</Badge>
                  <p className="text-xs text-gray-500 mt-1">
                    {formatTime(result.timestamp)}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}