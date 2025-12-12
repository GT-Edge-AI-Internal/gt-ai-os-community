'use client';

import React, { useState } from 'react';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { 
  Settings, 
  GitBranch, 
  RotateCcw, 
  Zap, 
  Filter,
  Calculator
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface LogicNodeData {
  logic_type: 'decision' | 'loop' | 'transform' | 'aggregate' | 'filter';
  name: string;
  config: Record<string, any>;
}

interface WorkflowNode {
  id: string;
  type: string;
  position: { x: number; y: number };
  data: LogicNodeData;
  selected?: boolean;
}

interface LogicNodeProps {
  node: WorkflowNode;
  selected: boolean;
  connecting: boolean;
  onClick: () => void;
  onUpdate: (updates: Partial<WorkflowNode>) => void;
  onStartConnection: () => void;
  onFinishConnection: () => void;
  readOnly?: boolean;
}

export function LogicNode({
  node,
  selected,
  connecting,
  onClick,
  onUpdate,
  onStartConnection,
  onFinishConnection,
  readOnly = false
}: LogicNodeProps) {
  const [isEditing, setIsEditing] = useState(false);

  const handleNodeClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (connecting) {
      onFinishConnection();
    } else {
      onClick();
    }
  };

  const handleConfigUpdate = (field: string, value: any) => {
    onUpdate({
      data: {
        ...node.data,
        [field]: value
      }
    });
  };

  const getLogicIcon = (logicType: string) => {
    switch (logicType) {
      case 'decision':
        return GitBranch;
      case 'loop':
        return RotateCcw;
      case 'transform':
        return Zap;
      case 'aggregate':
        return Calculator;
      case 'filter':
        return Filter;
      default:
        return GitBranch;
    }
  };

  const getLogicColor = (logicType: string) => {
    switch (logicType) {
      case 'decision':
        return 'bg-yellow-100 text-yellow-700 border-yellow-300';
      case 'loop':
        return 'bg-indigo-100 text-indigo-700 border-indigo-300';
      case 'transform':
        return 'bg-pink-100 text-pink-700 border-pink-300';
      case 'aggregate':
        return 'bg-cyan-100 text-cyan-700 border-cyan-300';
      case 'filter':
        return 'bg-teal-100 text-teal-700 border-teal-300';
      default:
        return 'bg-gray-100 text-gray-600 border-gray-300';
    }
  };

  const IconComponent = getLogicIcon(node.data.logic_type);

  return (
    <Card 
      className={cn(
        'workflow-node logic-node cursor-pointer transition-all duration-200 w-64 min-h-32',
        'hover:shadow-lg',
        selected && 'ring-2 ring-blue-500 shadow-lg',
        connecting && 'ring-2 ring-green-500 animate-pulse',
        readOnly && 'cursor-default'
      )}
      onClick={handleNodeClick}
    >
      {/* Input and Output ports */}
      <div className="absolute left-0 top-1/2 w-3 h-3 -ml-1.5 -mt-1.5">
        <div className="w-full h-full rounded-full bg-gray-400 hover:bg-blue-500 cursor-pointer transition-colors" />
      </div>
      
      <div className="absolute right-0 top-1/2 w-3 h-3 -mr-1.5 -mt-1.5">
        <div 
          className="w-full h-full rounded-full bg-gray-400 hover:bg-blue-500 cursor-pointer transition-colors"
          onClick={(e) => {
            e.stopPropagation();
            onStartConnection();
          }}
        />
      </div>

      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className={cn(
              'w-8 h-8 rounded-full border-2 flex items-center justify-center',
              getLogicColor(node.data.logic_type)
            )}>
              <IconComponent className="h-4 w-4" />
            </div>
            
            <div>
              <h3 className="font-medium text-sm text-gray-900 truncate">
                {node.data.name}
              </h3>
              <p className="text-xs text-gray-500">Logic</p>
            </div>
          </div>

          {!readOnly && (
            <Button
              size="sm"
              variant="ghost"
              onClick={(e) => {
                e.stopPropagation();
                setIsEditing(!isEditing);
              }}
            >
              <Settings className="h-4 w-4" />
            </Button>
          )}
        </div>
      </CardHeader>

      <CardContent className="space-y-3">
        {isEditing && (
          <div className="space-y-3">
            <div>
              <label className="text-xs font-medium text-gray-700 block mb-1">
                Logic Type
              </label>
              <select
                value={node.data.logic_type}
                onChange={(e) => handleConfigUpdate('logic_type', (e as React.ChangeEvent<HTMLSelectElement>).target.value)}
                className="w-full text-xs border border-gray-300 rounded px-2 py-1"
              >
                <option value="decision">Decision</option>
                <option value="loop">Loop</option>
                <option value="transform">Transform</option>
                <option value="aggregate">Aggregate</option>
                <option value="filter">Filter</option>
              </select>
            </div>

            <div>
              <label className="text-xs font-medium text-gray-700 block mb-1">Name</label>
              <Input
                value={node.data.name}
                onChange={(e) => handleConfigUpdate('name', (e as React.ChangeEvent<HTMLSelectElement>).target.value)}
                className="text-xs"
              />
            </div>

            {node.data.logic_type === 'decision' && (
              <div>
                <label className="text-xs font-medium text-gray-700 block mb-1">
                  Condition
                </label>
                <textarea
                  value={node.data.config.condition || ''}
                  onChange={(e) => handleConfigUpdate('config', {...node.data.config, condition: (e as React.ChangeEvent<HTMLSelectElement>).target.value})}
                  className="w-full text-xs border border-gray-300 rounded px-2 py-1 font-mono"
                  placeholder="input.value > 10"
                  rows={2}
                />
              </div>
            )}
          </div>
        )}

        {!isEditing && (
          <div className="space-y-2">
            <p className="text-xs text-gray-600">
              {node.data.logic_type.charAt(0).toUpperCase() + node.data.logic_type.slice(1)} logic node
            </p>
            
            <div className="flex justify-between items-center pt-2 border-t border-gray-200">
              <div className="flex items-center gap-1">
                <div className="w-2 h-2 rounded-full bg-green-400" />
                <span className="text-xs text-gray-500">Ready</span>
              </div>
              
              <Badge 
                variant="secondary" 
                className={cn('text-xs px-1 py-0', getLogicColor(node.data.logic_type))}
              >
                {node.data.logic_type}
              </Badge>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}