'use client';

import React, { useState, useCallback, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Separator } from '@/components/ui/separator';
import { AgentNode } from './nodes/AgentNode';
import { TriggerNode } from './nodes/TriggerNode';
import { IntegrationNode } from './nodes/IntegrationNode';
import { LogicNode } from './nodes/LogicNode';
import { OutputNode } from './nodes/OutputNode';
import { 
  Plus, Save, Play, ZoomIn, ZoomOut, Grid, Move, MousePointer, 
  Undo, Redo, Copy, Trash2, Settings, Eye, EyeOff, Layers,
  Bot, Zap, Link, GitBranch, Target, Activity, AlertTriangle,
  Check, X, Info, RotateCcw, Maximize2, Minimize2
} from 'lucide-react';
import { cn, formatTime } from '@/lib/utils';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';

interface Position {
  x: number;
  y: number;
}

interface WorkflowNode {
  id: string;
  type: 'agent' | 'trigger' | 'integration' | 'logic' | 'output';
  position: Position;
  data: Record<string, any>;
  selected?: boolean;
  errors?: string[];
  warnings?: string[];
}

interface WorkflowEdge {
  id: string;
  source: string;
  target: string;
  sourceHandle?: string;
  targetHandle?: string;
  animated?: boolean;
  style?: Record<string, any>;
}

interface WorkflowDefinition {
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  config?: Record<string, any>;
}

interface WorkflowValidationResult {
  isValid: boolean;
  errors: Array<{ nodeId?: string; edgeId?: string; message: string; type: 'error' | 'warning' }>;
}

interface EnhancedWorkflowCanvasProps {
  workflow?: {
    id: string;
    name: string;
    definition: WorkflowDefinition;
  };
  readOnly?: boolean;
  onSave?: (definition: WorkflowDefinition) => void;
  onExecute?: (definition: WorkflowDefinition) => void;
  onValidate?: (definition: WorkflowDefinition) => WorkflowValidationResult;
  autoSave?: boolean;
  autoSaveInterval?: number;
  className?: string;
}

export function EnhancedWorkflowCanvas({ 
  workflow, 
  readOnly = false, 
  onSave, 
  onExecute,
  onValidate,
  autoSave = true,
  autoSaveInterval = 5000,
  className
}: EnhancedWorkflowCanvasProps) {
  const canvasRef = useRef<HTMLDivElement>(null);
  const [nodes, setNodes] = useState<WorkflowNode[]>(workflow?.definition?.nodes || []);
  const [edges, setEdges] = useState<WorkflowEdge[]>(workflow?.definition?.edges || []);
  const [selectedNodes, setSelectedNodes] = useState<Set<string>>(new Set());
  const [selectedNode, setSelectedNode] = useState<WorkflowNode | null>(null);
  const [isConnecting, setIsConnecting] = useState(false);
  const [connectionStart, setConnectionStart] = useState<string | null>(null);
  const [draggedNode, setDraggedNode] = useState<string | null>(null);
  const [dragOffset, setDragOffset] = useState<Position>({ x: 0, y: 0 });
  const [canvasOffset, setCanvasOffset] = useState<Position>({ x: 0, y: 0 });
  const [zoom, setZoom] = useState(1);
  const [mode, setMode] = useState<'select' | 'pan'>('select');
  const [showGrid, setShowGrid] = useState(true);
  const [showMinimap, setShowMinimap] = useState(true);
  const [showPropertyPanel, setShowPropertyPanel] = useState(false);
  const [validationResult, setValidationResult] = useState<WorkflowValidationResult | null>(null);
  const [isDirty, setIsDirty] = useState(false);
  const [isAutoSaving, setIsAutoSaving] = useState(false);
  const [lastSaved, setLastSaved] = useState<Date | null>(null);
  const [history, setHistory] = useState<WorkflowDefinition[]>([{ nodes: [], edges: [] }]);
  const [historyIndex, setHistoryIndex] = useState(0);

  // Auto-save functionality
  useEffect(() => {
    if (autoSave && isDirty && onSave && !readOnly) {
      const timer = setTimeout(async () => {
        setIsAutoSaving(true);
        try {
          await onSave({ nodes, edges });
          setLastSaved(new Date());
          setIsDirty(false);
        } catch (error) {
          console.error('Auto-save failed:', error);
        } finally {
          setIsAutoSaving(false);
        }
      }, autoSaveInterval);

      return () => clearTimeout(timer);
    }
  }, [nodes, edges, isDirty, autoSave, autoSaveInterval, onSave, readOnly]);

  // Validation
  useEffect(() => {
    if (onValidate) {
      const result = onValidate({ nodes, edges });
      setValidationResult(result);
    }
  }, [nodes, edges, onValidate]);

  // History management
  const saveToHistory = useCallback(() => {
    const newDefinition = { nodes: [...nodes], edges: [...edges] };
    const newHistory = history.slice(0, historyIndex + 1);
    newHistory.push(newDefinition);
    
    // Keep history to reasonable size
    if (newHistory.length > 50) {
      newHistory.shift();
    } else {
      setHistoryIndex(prev => prev + 1);
    }
    
    setHistory(newHistory);
  }, [nodes, edges, history, historyIndex]);

  const undo = useCallback(() => {
    if (historyIndex > 0) {
      const previousState = history[historyIndex - 1];
      setNodes(previousState.nodes);
      setEdges(previousState.edges);
      setHistoryIndex(prev => prev - 1);
      setIsDirty(true);
    }
  }, [history, historyIndex]);

  const redo = useCallback(() => {
    if (historyIndex < history.length - 1) {
      const nextState = history[historyIndex + 1];
      setNodes(nextState.nodes);
      setEdges(nextState.edges);
      setHistoryIndex(prev => prev + 1);
      setIsDirty(true);
    }
  }, [history, historyIndex]);

  // Enhanced drag and drop
  const handleNodeMouseDown = useCallback((e: React.MouseEvent, nodeId: string) => {
    if (readOnly || mode !== 'select') return;
    
    e.stopPropagation();
    const node = nodes.find(n => n.id === nodeId);
    if (!node) return;

    const rect = e.currentTarget.getBoundingClientRect();
    const offsetX = e.clientX - rect.left;
    const offsetY = e.clientY - rect.top;
    
    setDraggedNode(nodeId);
    setDragOffset({ x: offsetX, y: offsetY });
    
    const handleMouseMove = (moveEvent: MouseEvent) => {
      const canvasRect = canvasRef.current?.getBoundingClientRect();
      if (!canvasRect) return;

      const newX = (moveEvent.clientX - canvasRect.left - canvasOffset.x - offsetX) / zoom;
      const newY = (moveEvent.clientY - canvasRect.top - canvasOffset.y - offsetY) / zoom;

      setNodes(prev => prev.map(n => 
        n.id === nodeId ? { ...n, position: { x: newX, y: newY } } : n
      ));
      setIsDirty(true);
    };
    
    const handleMouseUp = () => {
      setDraggedNode(null);
      saveToHistory();
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
    
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
  }, [nodes, readOnly, mode, canvasOffset, zoom, saveToHistory]);

  // Canvas panning and zooming
  const handleCanvasMouseDown = useCallback((e: React.MouseEvent) => {
    if (mode === 'pan') {
      const startX = e.clientX - canvasOffset.x;
      const startY = e.clientY - canvasOffset.y;
      
      const handleMouseMove = (moveEvent: MouseEvent) => {
        setCanvasOffset({
          x: moveEvent.clientX - startX,
          y: moveEvent.clientY - startY
        });
      };
      
      const handleMouseUp = () => {
        document.removeEventListener('mousemove', handleMouseMove);
        document.removeEventListener('mouseup', handleMouseUp);
      };
      
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
    }
  }, [mode, canvasOffset]);

  // Node operations
  const addNode = useCallback((nodeType: WorkflowNode['type'], position?: Position) => {
    if (readOnly) return;
    
    const newNode: WorkflowNode = {
      id: `${nodeType}-${Date.now()}`,
      type: nodeType,
      position: position || { 
        x: (300 - canvasOffset.x) / zoom, 
        y: (200 - canvasOffset.y) / zoom 
      },
      data: getDefaultNodeData(nodeType)
    };
    
    setNodes(prev => [...prev, newNode]);
    setIsDirty(true);
    saveToHistory();
  }, [readOnly, canvasOffset, zoom, saveToHistory]);

  const deleteSelectedNodes = useCallback(() => {
    if (readOnly || selectedNodes.size === 0) return;
    
    setNodes(prev => prev.filter(node => !selectedNodes.has(node.id)));
    setEdges(prev => prev.filter(edge => 
      !selectedNodes.has(edge.source) && !selectedNodes.has(edge.target)
    ));
    setSelectedNodes(new Set());
    setSelectedNode(null);
    setIsDirty(true);
    saveToHistory();
  }, [readOnly, selectedNodes, saveToHistory]);

  const duplicateSelectedNodes = useCallback(() => {
    if (readOnly || selectedNodes.size === 0) return;
    
    const nodesToDuplicate = nodes.filter(node => selectedNodes.has(node.id));
    const newNodes = nodesToDuplicate.map(node => ({
      ...node,
      id: `${node.type}-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      position: { x: node.position.x + 50, y: node.position.y + 50 },
      selected: false
    }));
    
    setNodes(prev => [...prev, ...newNodes]);
    setSelectedNodes(new Set(newNodes.map(n => n.id)));
    setIsDirty(true);
    saveToHistory();
  }, [readOnly, selectedNodes, nodes, saveToHistory]);

  // Node selection
  const handleNodeClick = useCallback((nodeId: string, multiSelect = false) => {
    const node = nodes.find(n => n.id === nodeId);
    if (!node) return;
    
    if (multiSelect) {
      setSelectedNodes(prev => {
        const newSelection = new Set(prev);
        if (newSelection.has(nodeId)) {
          newSelection.delete(nodeId);
        } else {
          newSelection.add(nodeId);
        }
        return newSelection;
      });
    } else {
      setSelectedNodes(new Set([nodeId]));
      setSelectedNode(node);
      setShowPropertyPanel(true);
    }
  }, [nodes]);

  // Edge creation with validation
  const startConnection = useCallback((nodeId: string) => {
    if (readOnly) return;
    
    setIsConnecting(true);
    setConnectionStart(nodeId);
  }, [readOnly]);

  const finishConnection = useCallback((targetNodeId: string) => {
    if (readOnly || !connectionStart || connectionStart === targetNodeId) {
      setIsConnecting(false);
      setConnectionStart(null);
      return;
    }
    
    // Validate connection
    const sourceNode = nodes.find(n => n.id === connectionStart);
    const targetNode = nodes.find(n => n.id === targetNodeId);
    
    if (!sourceNode || !targetNode) return;
    
    // Prevent cycles (basic check)
    const wouldCreateCycle = edges.some(edge => 
      edge.source === targetNodeId && edge.target === connectionStart
    );
    
    if (wouldCreateCycle) {
      // Could show error message here
      setIsConnecting(false);
      setConnectionStart(null);
      return;
    }
    
    const newEdge: WorkflowEdge = {
      id: `edge-${connectionStart}-${targetNodeId}`,
      source: connectionStart,
      target: targetNodeId,
      animated: true
    };
    
    setEdges(prev => [...prev, newEdge]);
    setIsConnecting(false);
    setConnectionStart(null);
    setIsDirty(true);
    saveToHistory();
  }, [readOnly, connectionStart, nodes, edges, saveToHistory]);

  // Node update
  const updateNode = useCallback((nodeId: string, updates: Partial<WorkflowNode>) => {
    if (readOnly) return;
    
    setNodes(prev => prev.map(node => 
      node.id === nodeId ? { ...node, ...updates } : node
    ));
    
    // Update selected node if it's the one being updated
    if (selectedNode?.id === nodeId) {
      setSelectedNode(prev => prev ? { ...prev, ...updates } : null);
    }
    
    setIsDirty(true);
  }, [readOnly, selectedNode]);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
        return;
      }

      if (e.key === 'Delete' || e.key === 'Backspace') {
        deleteSelectedNodes();
      } else if (e.key === 'Escape') {
        setSelectedNodes(new Set());
        setSelectedNode(null);
        setIsConnecting(false);
        setConnectionStart(null);
        setShowPropertyPanel(false);
      } else if ((e.ctrlKey || e.metaKey)) {
        if (e.key === 's') {
          e.preventDefault();
          if (onSave && !readOnly) {
            onSave({ nodes, edges });
            setLastSaved(new Date());
            setIsDirty(false);
          }
        } else if (e.key === 'z' && !e.shiftKey) {
          e.preventDefault();
          undo();
        } else if (e.key === 'z' && e.shiftKey || e.key === 'y') {
          e.preventDefault();
          redo();
        } else if (e.key === 'd') {
          e.preventDefault();
          duplicateSelectedNodes();
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [deleteSelectedNodes, onSave, nodes, edges, readOnly, undo, redo, duplicateSelectedNodes]);

  // Zoom controls
  const handleZoomIn = () => setZoom(prev => Math.min(prev * 1.2, 3));
  const handleZoomOut = () => setZoom(prev => Math.max(prev / 1.2, 0.1));
  const resetZoom = () => setZoom(1);

  // Auto-layout
  const autoLayout = useCallback(() => {
    if (readOnly) return;
    
    // Simple force-directed layout
    const layoutNodes = [...nodes];
    const SPACING = 200;
    
    layoutNodes.forEach((node, index) => {
      const col = index % 3;
      const row = Math.floor(index / 3);
      node.position = {
        x: col * SPACING + 100,
        y: row * SPACING + 100
      };
    });
    
    setNodes(layoutNodes);
    setIsDirty(true);
    saveToHistory();
  }, [nodes, readOnly, saveToHistory]);

  const getValidationIcon = (type: 'error' | 'warning') => {
    return type === 'error' ? (
      <AlertTriangle className="w-4 h-4 text-red-500" />
    ) : (
      <Info className="w-4 h-4 text-yellow-500" />
    );
  };

  return (
    <TooltipProvider>
      <div className={cn("workflow-canvas-container h-full flex flex-col bg-gray-50", className)}>
        {/* Enhanced Toolbar */}
        <div className="workflow-toolbar p-4 bg-gt-white border-b border-gray-200 flex items-center justify-between shadow-sm">
          <div className="flex items-center gap-3">
            {/* Mode Toggle */}
            <div className="flex bg-gray-100 rounded-lg p-1">
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant={mode === 'select' ? 'primary' : 'ghost'}
                    size="sm"
                    onClick={() => setMode('select')}
                  >
                    <MousePointer className="h-4 w-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Select Mode</TooltipContent>
              </Tooltip>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant={mode === 'pan' ? 'primary' : 'ghost'}
                    size="sm"
                    onClick={() => setMode('pan')}
                  >
                    <Move className="h-4 w-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Pan Mode</TooltipContent>
              </Tooltip>
            </div>

            <Separator orientation="vertical" className="h-6" />

            {/* Node Creation */}
            <div className="flex gap-1">
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button size="sm" variant="secondary" disabled={readOnly}>
                    <Plus className="h-4 w-4 mr-1" />
                    Add Node
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent>
                  <DropdownMenuItem onClick={() => addNode('trigger')}>
                    <Zap className="h-4 w-4 mr-2" />
                    Trigger
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => addNode('agent')}>
                    <Bot className="h-4 w-4 mr-2" />
                    Agent
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => addNode('integration')}>
                    <Link className="h-4 w-4 mr-2" />
                    Integration
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => addNode('logic')}>
                    <GitBranch className="h-4 w-4 mr-2" />
                    Logic
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => addNode('output')}>
                    <Target className="h-4 w-4 mr-2" />
                    Output
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>

            <Separator orientation="vertical" className="h-6" />

            {/* History Controls */}
            <div className="flex gap-1">
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button 
                    size="sm" 
                    variant="secondary" 
                    onClick={undo}
                    disabled={historyIndex <= 0}
                  >
                    <Undo className="h-4 w-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Undo (Ctrl+Z)</TooltipContent>
              </Tooltip>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button 
                    size="sm" 
                    variant="secondary" 
                    onClick={redo}
                    disabled={historyIndex >= history.length - 1}
                  >
                    <Redo className="h-4 w-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Redo (Ctrl+Y)</TooltipContent>
              </Tooltip>
            </div>

            {/* Edit Actions */}
            <div className="flex gap-1">
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button 
                    size="sm" 
                    variant="secondary" 
                    onClick={duplicateSelectedNodes}
                    disabled={selectedNodes.size === 0 || readOnly}
                  >
                    <Copy className="h-4 w-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Duplicate (Ctrl+D)</TooltipContent>
              </Tooltip>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button 
                    size="sm" 
                    variant="secondary" 
                    onClick={deleteSelectedNodes}
                    disabled={selectedNodes.size === 0 || readOnly}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Delete (Del)</TooltipContent>
              </Tooltip>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {/* Validation Status */}
            {validationResult && (
              <div className="flex items-center gap-2">
                {validationResult.errors.filter(e => e.type === 'error').length > 0 && (
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <div className="flex items-center gap-1 text-red-600">
                        <AlertTriangle className="w-4 h-4" />
                        <span className="text-sm font-medium">
                          {validationResult.errors.filter(e => e.type === 'error').length}
                        </span>
                      </div>
                    </TooltipTrigger>
                    <TooltipContent>
                      <div className="space-y-1">
                        {validationResult.errors.filter(e => e.type === 'error').map((error, idx) => (
                          <div key={idx} className="text-xs">{error.message}</div>
                        ))}
                      </div>
                    </TooltipContent>
                  </Tooltip>
                )}
                {validationResult.errors.filter(e => e.type === 'warning').length > 0 && (
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <div className="flex items-center gap-1 text-yellow-600">
                        <Info className="w-4 h-4" />
                        <span className="text-sm font-medium">
                          {validationResult.errors.filter(e => e.type === 'warning').length}
                        </span>
                      </div>
                    </TooltipTrigger>
                    <TooltipContent>
                      <div className="space-y-1">
                        {validationResult.errors.filter(e => e.type === 'warning').map((error, idx) => (
                          <div key={idx} className="text-xs">{error.message}</div>
                        ))}
                      </div>
                    </TooltipContent>
                  </Tooltip>
                )}
                {validationResult.isValid && (
                  <div className="flex items-center gap-1 text-green-600">
                    <Check className="w-4 h-4" />
                    <span className="text-sm font-medium">Valid</span>
                  </div>
                )}
              </div>
            )}

            {/* Save Status */}
            <div className="flex items-center gap-2 text-sm text-gray-500">
              {isAutoSaving && (
                <div className="flex items-center gap-1">
                  <Activity className="w-3 h-3 animate-pulse" />
                  <span>Saving...</span>
                </div>
              )}
              {isDirty && !isAutoSaving && (
                <div className="flex items-center gap-1">
                  <div className="w-2 h-2 bg-orange-500 rounded-full" />
                  <span>Unsaved changes</span>
                </div>
              )}
              {lastSaved && !isDirty && !isAutoSaving && (
                <div className="flex items-center gap-1">
                  <Check className="w-3 h-3 text-green-500" />
                  <span>Saved {formatTime(lastSaved)}</span>
                </div>
              )}
            </div>

            <Separator orientation="vertical" className="h-6" />

            {/* View Controls */}
            <div className="flex items-center gap-2">
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button 
                    size="sm" 
                    variant="secondary" 
                    onClick={() => setShowGrid(!showGrid)}
                  >
                    <Grid className={cn("h-4 w-4", showGrid && "text-blue-600")} />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Toggle Grid</TooltipContent>
              </Tooltip>
              
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button 
                    size="sm" 
                    variant="secondary" 
                    onClick={() => setShowMinimap(!showMinimap)}
                  >
                    <Layers className={cn("h-4 w-4", showMinimap && "text-blue-600")} />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Toggle Minimap</TooltipContent>
              </Tooltip>

              <Tooltip>
                <TooltipTrigger asChild>
                  <Button 
                    size="sm" 
                    variant="secondary" 
                    onClick={() => setShowPropertyPanel(!showPropertyPanel)}
                  >
                    <Settings className={cn("h-4 w-4", showPropertyPanel && "text-blue-600")} />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Toggle Properties</TooltipContent>
              </Tooltip>
            </div>

            {/* Zoom Controls */}
            <div className="flex items-center gap-1">
              <Button size="sm" variant="secondary" onClick={handleZoomOut}>
                <ZoomOut className="h-4 w-4" />
              </Button>
              <Button 
                size="sm" 
                variant="secondary" 
                onClick={resetZoom}
                className="min-w-[60px]"
              >
                {Math.round(zoom * 100)}%
              </Button>
              <Button size="sm" variant="secondary" onClick={handleZoomIn}>
                <ZoomIn className="h-4 w-4" />
              </Button>
            </div>

            <Separator orientation="vertical" className="h-6" />

            {/* Layout & Actions */}
            <Button size="sm" variant="secondary" onClick={autoLayout} disabled={readOnly}>
              <RotateCcw className="h-4 w-4 mr-1" />
              Auto Layout
            </Button>

            <Button size="sm" onClick={() => onSave?.({ nodes, edges })} disabled={readOnly}>
              <Save className="h-4 w-4 mr-1" />
              Save
            </Button>
            
            <Button size="sm" onClick={() => onExecute?.({ nodes, edges })}>
              <Play className="h-4 w-4 mr-1" />
              Execute
            </Button>
          </div>
        </div>

        <div className="flex-1 flex">
          {/* Main Canvas */}
          <div className="flex-1 relative">
            <div 
              ref={canvasRef}
              className="workflow-canvas h-full relative overflow-hidden cursor-pointer"
              onMouseDown={handleCanvasMouseDown}
              style={{ 
                cursor: mode === 'pan' ? 'grab' : 'default',
                backgroundImage: showGrid ? `
                  radial-gradient(circle, #e2e8f0 1px, transparent 1px)
                ` : undefined,
                backgroundSize: showGrid ? `${20 * zoom}px ${20 * zoom}px` : undefined,
                backgroundPosition: `${canvasOffset.x}px ${canvasOffset.y}px`
              }}
            >
              <div
                className="canvas-content"
                style={{
                  transform: `translate(${canvasOffset.x}px, ${canvasOffset.y}px) scale(${zoom})`,
                  transformOrigin: '0 0',
                  width: '100%',
                  height: '100%',
                  position: 'relative'
                }}
              >
                {/* Render edges with animations */}
                <svg
                  className="absolute inset-0 pointer-events-none"
                  style={{ width: '100%', height: '100%' }}
                >
                  {edges.map(edge => {
                    const sourceNode = nodes.find(n => n.id === edge.source);
                    const targetNode = nodes.find(n => n.id === edge.target);
                    
                    if (!sourceNode || !targetNode) return null;
                    
                    const sourcePosition = sourceNode.position || { x: 100, y: 100 };
                    const targetPosition = targetNode.position || { x: 100, y: 100 };
                    
                    const startX = sourcePosition.x + 128; // Node width/2
                    const startY = sourcePosition.y + 40; // Node height/2
                    const endX = targetPosition.x;
                    const endY = targetPosition.y + 40;
                    
                    const controlX1 = startX + (endX - startX) * 0.5;
                    const controlX2 = endX - (endX - startX) * 0.5;
                    
                    const pathData = `M ${startX} ${startY} C ${controlX1} ${startY}, ${controlX2} ${endY}, ${endX} ${endY}`;
                    
                    return (
                      <g key={edge.id}>
                        <path
                          d={pathData}
                          stroke="#6b7280"
                          strokeWidth="2"
                          fill="none"
                          markerEnd="url(#arrowhead)"
                          className={cn(
                            "transition-all duration-200",
                            edge.animated && "animate-pulse"
                          )}
                        />
                        {/* Connection point indicators */}
                        <circle
                          cx={endX}
                          cy={endY}
                          r="4"
                          fill="#6b7280"
                          className="opacity-0 hover:opacity-100 transition-opacity"
                        />
                      </g>
                    );
                  })}
                  
                  {/* Connection preview */}
                  {isConnecting && connectionStart && (
                    <line
                      x1={nodes.find(n => n.id === connectionStart)?.position.x || 0 + 128}
                      y1={nodes.find(n => n.id === connectionStart)?.position.y || 0 + 40}
                      x2={canvasOffset.x}
                      y2={canvasOffset.y}
                      stroke="#3b82f6"
                      strokeWidth="2"
                      strokeDasharray="5,5"
                      className="animate-pulse"
                    />
                  )}
                  
                  {/* Arrow marker */}
                  <defs>
                    <marker
                      id="arrowhead"
                      markerWidth="10"
                      markerHeight="7"
                      refX="10"
                      refY="3.5"
                      orient="auto"
                    >
                      <polygon
                        points="0 0, 10 3.5, 0 7"
                        fill="#6b7280"
                      />
                    </marker>
                  </defs>
                </svg>

                {/* Render nodes with enhanced interactions */}
                <AnimatePresence>
                  {nodes.map(node => {
                    const NodeComponent = getNodeComponent(node.type);
                    const isSelected = selectedNodes.has(node.id);
                    const position = node.position || { x: 100, y: 100 };
                    
                    return (
                      <motion.div
                        key={node.id}
                        className="absolute"
                        style={{
                          left: position.x,
                          top: position.y,
                          zIndex: isSelected ? 10 : 1
                        }}
                        initial={{ opacity: 0, scale: 0.8 }}
                        animate={{ 
                          opacity: 1, 
                          scale: isSelected ? 1.05 : 1,
                          boxShadow: isSelected ? '0 10px 25px rgba(0,0,0,0.15)' : '0 2px 10px rgba(0,0,0,0.1)'
                        }}
                        exit={{ opacity: 0, scale: 0.8 }}
                        transition={{ duration: 0.2 }}
                        onMouseDown={(e) => handleNodeMouseDown(e, node.id)}
                      >
                        <div className="relative">
                          {/* Error/Warning indicators */}
                          {node.errors && node.errors.length > 0 && (
                            <div className="absolute -top-2 -right-2 z-20">
                              <AlertTriangle className="w-4 h-4 text-red-500 bg-gt-white rounded-full p-0.5" />
                            </div>
                          )}
                          {node.warnings && node.warnings.length > 0 && (
                            <div className="absolute -top-2 -left-2 z-20">
                              <Info className="w-4 h-4 text-yellow-500 bg-gt-white rounded-full p-0.5" />
                            </div>
                          )}
                          
                          <NodeComponent
                            node={node}
                            selected={isSelected}
                            connecting={isConnecting}
                            onClick={() => handleNodeClick(node.id)}
                            onUpdate={(updates) => updateNode(node.id, updates)}
                            onStartConnection={() => startConnection(node.id)}
                            onFinishConnection={() => finishConnection(node.id)}
                            readOnly={readOnly}
                          />
                        </div>
                      </motion.div>
                    );
                  })}
                </AnimatePresence>
              </div>
            </div>

            {/* Minimap */}
            {showMinimap && (
              <motion.div
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.8 }}
                className="absolute bottom-4 right-4 w-48 h-32 bg-gt-white border border-gray-300 rounded-lg shadow-lg overflow-hidden"
              >
                <div className="relative w-full h-full">
                  <div 
                    className="absolute inset-0 bg-gray-50"
                    style={{
                      backgroundImage: showGrid ? 'radial-gradient(circle, #e2e8f0 1px, transparent 1px)' : undefined,
                      backgroundSize: showGrid ? '10px 10px' : undefined
                    }}
                  >
                    {nodes.map(node => (
                      <div
                        key={node.id}
                        className={cn(
                          "absolute w-3 h-2 rounded-sm",
                          node.type === 'trigger' && "bg-yellow-500",
                          node.type === 'agent' && "bg-blue-500",
                          node.type === 'integration' && "bg-green-500",
                          node.type === 'logic' && "bg-purple-500",
                          node.type === 'output' && "bg-red-500"
                        )}
                        style={{
                          left: (node.position?.x || 0) * 0.1,
                          top: (node.position?.y || 0) * 0.1
                        }}
                      />
                    ))}
                    {/* Viewport indicator */}
                    <div 
                      className="absolute border-2 border-blue-500 bg-blue-500/20 rounded"
                      style={{
                        left: Math.max(0, -canvasOffset.x * 0.1),
                        top: Math.max(0, -canvasOffset.y * 0.1),
                        width: Math.min(192, 192 / zoom),
                        height: Math.min(128, 128 / zoom)
                      }}
                    />
                  </div>
                </div>
              </motion.div>
            )}

            {/* Connection indicator */}
            {isConnecting && connectionStart && (
              <div className="absolute top-4 left-1/2 transform -translate-x-1/2 bg-blue-100 border border-blue-300 rounded-lg px-3 py-2 text-sm text-blue-800">
                Connecting from <strong>{connectionStart}</strong>... Click target node to complete
              </div>
            )}
          </div>

          {/* Property Panel */}
          <AnimatePresence>
            {showPropertyPanel && (
              <motion.div
                initial={{ width: 0, opacity: 0 }}
                animate={{ width: 320, opacity: 1 }}
                exit={{ width: 0, opacity: 0 }}
                transition={{ duration: 0.3 }}
                className="bg-gt-white border-l border-gray-200 overflow-hidden"
              >
                <div className="p-4 h-full overflow-y-auto">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="font-semibold text-gray-900">Properties</h3>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => setShowPropertyPanel(false)}
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  </div>

                  {selectedNode ? (
                    <div className="space-y-4">
                      {/* Node Type */}
                      <div>
                        <Label className="text-xs font-medium text-gray-500 uppercase tracking-wide">
                          Node Type
                        </Label>
                        <div className="mt-1">
                          <Badge variant="secondary" className="capitalize">
                            {selectedNode.type}
                          </Badge>
                        </div>
                      </div>

                      {/* Node ID */}
                      <div>
                        <Label className="text-xs font-medium text-gray-500 uppercase tracking-wide">
                          Node ID
                        </Label>
                        <div className="mt-1 text-sm font-mono text-gray-700 bg-gray-50 px-2 py-1 rounded">
                          {selectedNode.id}
                        </div>
                      </div>

                      {/* Position */}
                      <div>
                        <Label className="text-xs font-medium text-gray-500 uppercase tracking-wide">
                          Position
                        </Label>
                        <div className="mt-1 grid grid-cols-2 gap-2">
                          <div>
                            <Label htmlFor="pos-x" className="text-xs">X</Label>
                            <Input
                              id="pos-x"
                              type="number"
                              value={Math.round(selectedNode.position?.x || 0)}
                              onChange={(e) => updateNode(selectedNode.id, {
                                position: { 
                                  ...selectedNode.position,
                                  x: parseInt(e.target.value) || 0
                                }
                              })}
                              className="text-xs"
                              disabled={readOnly}
                            />
                          </div>
                          <div>
                            <Label htmlFor="pos-y" className="text-xs">Y</Label>
                            <Input
                              id="pos-y"
                              type="number"
                              value={Math.round(selectedNode.position?.y || 0)}
                              onChange={(e) => updateNode(selectedNode.id, {
                                position: { 
                                  ...selectedNode.position,
                                  y: parseInt(e.target.value) || 0
                                }
                              })}
                              className="text-xs"
                              disabled={readOnly}
                            />
                          </div>
                        </div>
                      </div>

                      {/* Node-specific properties */}
                      <Separator />
                      
                      <div>
                        <Label className="text-xs font-medium text-gray-500 uppercase tracking-wide">
                          Configuration
                        </Label>
                        <div className="mt-2 space-y-3">
                          {Object.entries(selectedNode.data || {}).map(([key, value]) => (
                            <div key={key}>
                              <Label htmlFor={key} className="text-xs capitalize">
                                {key.replace(/_/g, ' ')}
                              </Label>
                              {typeof value === 'string' && value.length > 50 ? (
                                <Textarea
                                  id={key}
                                  value={value}
                                  onChange={(e) => updateNode(selectedNode.id, {
                                    data: { ...selectedNode.data, [key]: e.target.value }
                                  })}
                                  className="text-xs mt-1"
                                  rows={3}
                                  disabled={readOnly}
                                />
                              ) : (
                                <Input
                                  id={key}
                                  value={String(value)}
                                  onChange={(e) => updateNode(selectedNode.id, {
                                    data: { ...selectedNode.data, [key]: e.target.value }
                                  })}
                                  className="text-xs mt-1"
                                  disabled={readOnly}
                                />
                              )}
                            </div>
                          ))}
                        </div>
                      </div>

                      {/* Validation errors for this node */}
                      {validationResult?.errors.filter(e => e.nodeId === selectedNode.id).length > 0 && (
                        <div>
                          <Label className="text-xs font-medium text-red-500 uppercase tracking-wide">
                            Issues
                          </Label>
                          <div className="mt-2 space-y-2">
                            {validationResult.errors
                              .filter(e => e.nodeId === selectedNode.id)
                              .map((error, idx) => (
                                <div key={idx} className={cn(
                                  "flex items-start gap-2 p-2 rounded",
                                  error.type === 'error' ? "bg-red-50 text-red-700" : "bg-yellow-50 text-yellow-700"
                                )}>
                                  {getValidationIcon(error.type)}
                                  <span className="text-xs">{error.message}</span>
                                </div>
                              ))
                            }
                          </div>
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="text-center text-gray-500 py-8">
                      <Settings className="w-12 h-12 mx-auto mb-4 opacity-50" />
                      <p className="text-sm">Select a node to view properties</p>
                    </div>
                  )}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Status Bar */}
        <div className="status-bar p-2 bg-gt-white border-t border-gray-200 text-sm text-gray-600 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <span>Nodes: {nodes.length}</span>
            <span>Edges: {edges.length}</span>
            <span>Selected: {selectedNodes.size}</span>
            {validationResult && (
              <span className={cn(
                "flex items-center gap-1",
                validationResult.isValid ? "text-green-600" : "text-red-600"
              )}>
                {validationResult.isValid ? (
                  <Check className="w-3 h-3" />
                ) : (
                  <AlertTriangle className="w-3 h-3" />
                )}
                {validationResult.isValid ? "Valid" : `${validationResult.errors.length} issues`}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2 text-xs">
            {isConnecting && connectionStart && (
              <span className="text-blue-600">
                Connecting from {connectionStart}... Click target node
              </span>
            )}
            <span>Zoom: {Math.round(zoom * 100)}%</span>
          </div>
        </div>
      </div>
    </TooltipProvider>
  );
}

// Helper functions
function getDefaultNodeData(nodeType: WorkflowNode['type']): Record<string, any> {
  switch (nodeType) {
    case 'trigger':
      return { trigger_type: 'manual', name: 'Manual Trigger' };
    case 'agent':
      return { agent_id: '', confidence_threshold: 70, name: 'AI Agent' };
    case 'integration':
      return { integration_type: 'api', method: 'GET', name: 'API Integration' };
    case 'logic':
      return { logic_type: 'decision', name: 'Decision Logic' };
    case 'output':
      return { output_type: 'webhook', name: 'Webhook Output' };
    default:
      return { name: 'Unknown Node' };
  }
}

function getNodeComponent(nodeType: WorkflowNode['type']) {
  switch (nodeType) {
    case 'agent':
      return AgentNode;
    case 'trigger':
      return TriggerNode;
    case 'integration':
      return IntegrationNode;
    case 'logic':
      return LogicNode;
    case 'output':
      return OutputNode;
    default:
      return Card; // Fallback component
  }
}