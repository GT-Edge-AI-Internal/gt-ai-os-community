'use client';

import React, { useState, useCallback, useRef, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { AgentNode } from './nodes/AgentNode';
import { TriggerNode } from './nodes/TriggerNode';
import { IntegrationNode } from './nodes/IntegrationNode';
import { LogicNode } from './nodes/LogicNode';
import { OutputNode } from './nodes/OutputNode';
import { 
  Plus, 
  Save, 
  Play, 
  ZoomIn, 
  ZoomOut,
  Grid,
  Move,
  MousePointer
} from 'lucide-react';

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
}

interface WorkflowEdge {
  id: string;
  source: string;
  target: string;
  sourceHandle?: string;
  targetHandle?: string;
}

interface WorkflowDefinition {
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  config?: Record<string, any>;
}

interface WorkflowCanvasProps {
  workflow?: {
    id: string;
    name: string;
    definition: WorkflowDefinition;
  };
  readOnly?: boolean;
  onSave?: (definition: WorkflowDefinition) => void;
  onExecute?: (definition: WorkflowDefinition) => void;
}

export function WorkflowCanvas({ 
  workflow, 
  readOnly = false, 
  onSave, 
  onExecute 
}: WorkflowCanvasProps) {
  const canvasRef = useRef<HTMLDivElement>(null);
  const [nodes, setNodes] = useState<WorkflowNode[]>(workflow?.definition?.nodes || []);
  const [edges, setEdges] = useState<WorkflowEdge[]>(workflow?.definition?.edges || []);
  const [selectedNodes, setSelectedNodes] = useState<Set<string>>(new Set());
  const [isConnecting, setIsConnecting] = useState(false);
  const [connectionStart, setConnectionStart] = useState<string | null>(null);
  const [draggedNode, setDraggedNode] = useState<string | null>(null);
  const [canvasOffset, setCanvasOffset] = useState<Position>({ x: 0, y: 0 });
  const [zoom, setZoom] = useState(1);
  const [mode, setMode] = useState<'select' | 'pan'>('select');
  const [showGrid, setShowGrid] = useState(true);

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

  // Node creation
  const addNode = useCallback((nodeType: WorkflowNode['type'], position?: Position) => {
    if (readOnly) return;
    
    const newNode: WorkflowNode = {
      id: `${nodeType}-${Date.now()}`,
      type: nodeType,
      position: position || { x: 100, y: 100 },
      data: getDefaultNodeData(nodeType)
    };
    
    setNodes(prev => [...prev, newNode]);
  }, [readOnly]);

  // Node selection
  const handleNodeClick = useCallback((nodeId: string, multiSelect = false) => {
    setSelectedNodes(prev => {
      const newSelection = new Set(multiSelect ? prev : []);
      if (newSelection.has(nodeId)) {
        newSelection.delete(nodeId);
      } else {
        newSelection.add(nodeId);
      }
      return newSelection;
    });
  }, []);

  // Node deletion
  const deleteSelectedNodes = useCallback(() => {
    if (readOnly || selectedNodes.size === 0) return;
    
    setNodes(prev => prev.filter(node => !selectedNodes.has(node.id)));
    setEdges(prev => prev.filter(edge => 
      !selectedNodes.has(edge.source) && !selectedNodes.has(edge.target)
    ));
    setSelectedNodes(new Set());
  }, [readOnly, selectedNodes]);

  // Edge creation
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
    
    const newEdge: WorkflowEdge = {
      id: `edge-${connectionStart}-${targetNodeId}`,
      source: connectionStart,
      target: targetNodeId
    };
    
    setEdges(prev => [...prev, newEdge]);
    setIsConnecting(false);
    setConnectionStart(null);
  }, [readOnly, connectionStart]);

  // Node update
  const updateNode = useCallback((nodeId: string, updates: Partial<WorkflowNode>) => {
    if (readOnly) return;
    
    setNodes(prev => prev.map(node => 
      node.id === nodeId ? { ...node, ...updates } : node
    ));
  }, [readOnly]);

  // Save workflow
  const handleSave = useCallback(() => {
    if (onSave) {
      const definition: WorkflowDefinition = {
        nodes,
        edges,
        config: {}
      };
      onSave(definition);
    }
  }, [nodes, edges, onSave]);

  // Execute workflow
  const handleExecute = useCallback(() => {
    if (onExecute) {
      const definition: WorkflowDefinition = {
        nodes,
        edges,
        config: {}
      };
      onExecute(definition);
    }
  }, [nodes, edges, onExecute]);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Delete' || e.key === 'Backspace') {
        deleteSelectedNodes();
      } else if (e.key === 'Escape') {
        setSelectedNodes(new Set());
        setIsConnecting(false);
        setConnectionStart(null);
      } else if (e.ctrlKey || e.metaKey) {
        if (e.key === 's') {
          e.preventDefault();
          handleSave();
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [deleteSelectedNodes, handleSave]);

  // Zoom controls
  const handleZoomIn = () => setZoom(prev => Math.min(prev * 1.2, 3));
  const handleZoomOut = () => setZoom(prev => Math.max(prev / 1.2, 0.1));

  return (
    <div className="workflow-canvas-container h-full flex flex-col bg-gray-50">
      {/* Toolbar */}
      <div className="workflow-toolbar p-4 bg-white border-b border-gray-200 flex items-center justify-between">
        <div className="flex items-center gap-2">
          {/* Mode Toggle */}
          <div className="flex bg-gray-100 rounded-lg p-1">
            <Button
              variant={mode === 'select' ? 'default' : 'ghost'}
              size="sm"
              onClick={() => setMode('select')}
            >
              <MousePointer className="h-4 w-4" />
            </Button>
            <Button
              variant={mode === 'pan' ? 'default' : 'ghost'}
              size="sm"
              onClick={() => setMode('pan')}
            >
              <Move className="h-4 w-4" />
            </Button>
          </div>

          {/* Node Creation Buttons */}
          <div className="flex gap-1">
            <Button 
              size="sm" 
              variant="secondary"
              onClick={() => addNode('trigger')}
              disabled={readOnly}
            >
              <Plus className="h-4 w-4 mr-1" />
              Trigger
            </Button>
            <Button 
              size="sm" 
              variant="secondary"
              onClick={() => addNode('agent')}
              disabled={readOnly}
            >
              <Plus className="h-4 w-4 mr-1" />
              Agent
            </Button>
            <Button 
              size="sm" 
              variant="secondary"
              onClick={() => addNode('integration')}
              disabled={readOnly}
            >
              <Plus className="h-4 w-4 mr-1" />
              Integration
            </Button>
            <Button 
              size="sm" 
              variant="secondary"
              onClick={() => addNode('output')}
              disabled={readOnly}
            >
              <Plus className="h-4 w-4 mr-1" />
              Output
            </Button>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* View Controls */}
          <Button size="sm" variant="secondary" onClick={() => setShowGrid(!showGrid)}>
            <Grid className="h-4 w-4" />
          </Button>
          
          <div className="flex gap-1">
            <Button size="sm" variant="secondary" onClick={handleZoomOut}>
              <ZoomOut className="h-4 w-4" />
            </Button>
            <span className="px-2 py-1 text-sm bg-gray-100 rounded">
              {Math.round(zoom * 100)}%
            </span>
            <Button size="sm" variant="secondary" onClick={handleZoomIn}>
              <ZoomIn className="h-4 w-4" />
            </Button>
          </div>

          {/* Actions */}
          <Button size="sm" onClick={handleSave} disabled={readOnly}>
            <Save className="h-4 w-4 mr-1" />
            Save
          </Button>
          
          <Button size="sm" onClick={handleExecute}>
            <Play className="h-4 w-4 mr-1" />
            Execute
          </Button>
        </div>
      </div>

      {/* Canvas */}
      <div 
        ref={canvasRef}
        className="workflow-canvas flex-1 relative overflow-hidden cursor-pointer"
        onMouseDown={handleCanvasMouseDown}
        style={{ 
          cursor: mode === 'pan' ? 'grab' : 'default',
          backgroundImage: showGrid ? `
            radial-gradient(circle, #e2e8f0 1px, transparent 1px)
          ` : undefined,
          backgroundSize: showGrid ? '20px 20px' : undefined
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
          {/* Render edges */}
          <svg
            className="absolute inset-0 pointer-events-none"
            style={{ width: '100%', height: '100%' }}
          >
            {edges.map(edge => {
              const sourceNode = nodes.find(n => n.id === edge.source);
              const targetNode = nodes.find(n => n.id === edge.target);
              
              if (!sourceNode || !targetNode) return null;
              
              // Provide default positions if missing
              const sourcePosition = sourceNode.position || { x: 100, y: 100 };
              const targetPosition = targetNode.position || { x: 100, y: 100 };
              
              const startX = sourcePosition.x + 100; // Assuming node width of 200px
              const startY = sourcePosition.y + 40; // Middle of node
              const endX = targetPosition.x;
              const endY = targetPosition.y + 40;
              
              // Create bezier curve
              const controlX1 = startX + (endX - startX) * 0.5;
              const controlX2 = endX - (endX - startX) * 0.5;
              
              const pathData = `M ${startX} ${startY} C ${controlX1} ${startY}, ${controlX2} ${endY}, ${endX} ${endY}`;
              
              return (
                <path
                  key={edge.id}
                  d={pathData}
                  stroke="#6b7280"
                  strokeWidth="2"
                  fill="none"
                  markerEnd="url(#arrowhead)"
                />
              );
            })}
            
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

          {/* Render nodes */}
          {nodes.map(node => {
            const NodeComponent = getNodeComponent(node.type);
            const isSelected = selectedNodes.has(node.id);
            
            // Provide default position if missing
            const position = node.position || { x: 100, y: 100 };
            
            return (
              <div
                key={node.id}
                className="absolute"
                style={{
                  left: position.x,
                  top: position.y,
                  transform: isSelected ? 'scale(1.05)' : 'scale(1)',
                  transition: 'transform 0.2s ease',
                  zIndex: isSelected ? 10 : 1
                }}
              >
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
            );
          })}
        </div>
      </div>

      {/* Status Bar */}
      <div className="status-bar p-2 bg-white border-t border-gray-200 text-sm text-gray-600">
        Nodes: {nodes.length} | Edges: {edges.length} | Selected: {selectedNodes.size}
        {isConnecting && connectionStart && (
          <span className="ml-4 text-blue-600">
            Connecting from {connectionStart}... Click target node to complete connection
          </span>
        )}
      </div>
    </div>
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