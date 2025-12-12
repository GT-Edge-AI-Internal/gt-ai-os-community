'use client';

import React, { useState } from 'react';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { 
  Settings, 
  Send, 
  Mail, 
  HardDrive, 
  Bell,
  Webhook,
  Globe
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface OutputNodeData {
  output_type: 'webhook' | 'api' | 'email' | 'storage' | 'notification';
  name: string;
  config: Record<string, any>;
}

interface WorkflowNode {
  id: string;
  type: string;
  position: { x: number; y: number };
  data: OutputNodeData;
  selected?: boolean;
}

interface OutputNodeProps {
  node: WorkflowNode;
  selected: boolean;
  connecting: boolean;
  onClick: () => void;
  onUpdate: (updates: Partial<WorkflowNode>) => void;
  onStartConnection: () => void;
  onFinishConnection: () => void;
  readOnly?: boolean;
}

export function OutputNode({
  node,
  selected,
  connecting,
  onClick,
  onUpdate,
  onStartConnection,
  onFinishConnection,
  readOnly = false
}: OutputNodeProps) {
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

  const getOutputIcon = (outputType: string) => {
    switch (outputType) {
      case 'webhook':
        return Webhook;
      case 'api':
        return Globe;
      case 'email':
        return Mail;
      case 'storage':
        return HardDrive;
      case 'notification':
        return Bell;
      default:
        return Send;
    }
  };

  const getOutputColor = (outputType: string) => {
    switch (outputType) {
      case 'webhook':
        return 'bg-purple-100 text-purple-700 border-purple-300';
      case 'api':
        return 'bg-blue-100 text-blue-700 border-blue-300';
      case 'email':
        return 'bg-red-100 text-red-700 border-red-300';
      case 'storage':
        return 'bg-orange-100 text-orange-700 border-orange-300';
      case 'notification':
        return 'bg-green-100 text-green-700 border-green-300';
      default:
        return 'bg-gray-100 text-gray-600 border-gray-300';
    }
  };

  const IconComponent = getOutputIcon(node.data.output_type);

  return (
    <Card 
      className={cn(
        'workflow-node output-node cursor-pointer transition-all duration-200 w-64 min-h-32',
        'hover:shadow-lg',
        selected && 'ring-2 ring-blue-500 shadow-lg',
        connecting && 'ring-2 ring-green-500 animate-pulse',
        readOnly && 'cursor-default'
      )}
      onClick={handleNodeClick}
    >
      {/* Input port only - outputs are end nodes */}
      <div className="absolute left-0 top-1/2 w-3 h-3 -ml-1.5 -mt-1.5">
        <div className="w-full h-full rounded-full bg-red-400 hover:bg-red-500 cursor-pointer transition-colors" />
      </div>

      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className={cn(
              'w-8 h-8 rounded-full border-2 flex items-center justify-center',
              getOutputColor(node.data.output_type)
            )}>
              <IconComponent className="h-4 w-4" />
            </div>
            
            <div>
              <h3 className="font-medium text-sm text-gray-900 truncate">
                {node.data.name}
              </h3>
              <p className="text-xs text-gray-500">Output</p>
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
                Output Type
              </label>
              <select
                value={node.data.output_type}
                onChange={(e) => handleConfigUpdate('output_type', (e as React.ChangeEvent<HTMLSelectElement>).target.value)}
                className="w-full text-xs border border-gray-300 rounded px-2 py-1"
              >
                <option value="webhook">Webhook</option>
                <option value="api">API Call</option>
                <option value="email">Email</option>
                <option value="storage">Storage</option>
                <option value="notification">Notification</option>
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

            {(node.data.output_type === 'webhook' || node.data.output_type === 'api') && (
              <div>
                <label className="text-xs font-medium text-gray-700 block mb-1">URL</label>
                <Input
                  value={node.data.config.url || ''}
                  onChange={(e) => handleConfigUpdate('config', {...node.data.config, url: (e as React.ChangeEvent<HTMLSelectElement>).target.value})}
                  className="text-xs"
                  placeholder="https://api.example.com/endpoint"
                />
              </div>
            )}

            {node.data.output_type === 'email' && (
              <div>
                <label className="text-xs font-medium text-gray-700 block mb-1">Email</label>
                <Input
                  value={node.data.config.email || ''}
                  onChange={(e) => handleConfigUpdate('config', {...node.data.config, email: (e as React.ChangeEvent<HTMLSelectElement>).target.value})}
                  className="text-xs"
                  placeholder="user@example.com"
                />
              </div>
            )}
          </div>
        )}

        {!isEditing && (
          <div className="space-y-2">
            <p className="text-xs text-gray-600">
              Send results to {node.data.output_type}
            </p>
            
            <div className="flex justify-between items-center pt-2 border-t border-gray-200">
              <div className="flex items-center gap-1">
                <div className="w-2 h-2 rounded-full bg-orange-400" />
                <span className="text-xs text-gray-500">Output</span>
              </div>
              
              <Badge 
                variant="secondary" 
                className={cn('text-xs px-1 py-0', getOutputColor(node.data.output_type))}
              >
                {node.data.output_type}
              </Badge>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}