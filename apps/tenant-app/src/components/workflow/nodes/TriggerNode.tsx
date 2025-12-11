'use client';

import React, { useState } from 'react';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { 
  Play, 
  Settings, 
  Webhook, 
  Clock, 
  Zap, 
  Globe,
  Calendar
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface TriggerNodeData {
  trigger_type: 'manual' | 'webhook' | 'cron' | 'event' | 'api';
  name: string;
  config: Record<string, any>;
  webhook_url?: string;
  cron_schedule?: string;
  event_source?: string;
}

interface WorkflowNode {
  id: string;
  type: string;
  position: { x: number; y: number };
  data: TriggerNodeData;
  selected?: boolean;
}

interface TriggerNodeProps {
  node: WorkflowNode;
  selected: boolean;
  connecting: boolean;
  onClick: () => void;
  onUpdate: (updates: Partial<WorkflowNode>) => void;
  onStartConnection: () => void;
  onFinishConnection: () => void;
  readOnly?: boolean;
}

export function TriggerNode({
  node,
  selected,
  connecting,
  onClick,
  onUpdate,
  onStartConnection,
  onFinishConnection,
  readOnly = false
}: TriggerNodeProps) {
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

  const handleTriggerTypeChange = (triggerType: TriggerNodeData['trigger_type']) => {
    const defaultConfigs = {
      manual: {},
      webhook: { method: 'POST', authentication: 'none' },
      cron: { schedule: '0 0 * * *', timezone: 'UTC' },
      event: { source: '', filters: {} },
      api: { endpoint: '', method: 'POST' }
    };

    onUpdate({
      data: {
        ...node.data,
        trigger_type: triggerType,
        config: defaultConfigs[triggerType],
        name: `${triggerType.charAt(0).toUpperCase() + triggerType.slice(1)} Trigger`
      }
    });
  };

  const getTriggerIcon = (triggerType: string) => {
    switch (triggerType) {
      case 'manual':
        return Play;
      case 'webhook':
        return Webhook;
      case 'cron':
        return Clock;
      case 'event':
        return Zap;
      case 'api':
        return Globe;
      default:
        return Play;
    }
  };

  const getTriggerColor = (triggerType: string) => {
    switch (triggerType) {
      case 'manual':
        return 'bg-blue-100 text-blue-700 border-blue-300';
      case 'webhook':
        return 'bg-purple-100 text-purple-700 border-purple-300';
      case 'cron':
        return 'bg-orange-100 text-orange-700 border-orange-300';
      case 'event':
        return 'bg-green-100 text-green-700 border-green-300';
      case 'api':
        return 'bg-red-100 text-red-700 border-red-300';
      default:
        return 'bg-gray-100 text-gray-600 border-gray-300';
    }
  };

  const getTriggerDescription = (triggerType: string) => {
    switch (triggerType) {
      case 'manual':
        return 'Triggered manually by user';
      case 'webhook':
        return 'HTTP webhook endpoint';
      case 'cron':
        return 'Scheduled execution';
      case 'event':
        return 'Event-based trigger';
      case 'api':
        return 'API endpoint trigger';
      default:
        return 'Unknown trigger';
    }
  };

  const IconComponent = getTriggerIcon(node.data.trigger_type);

  return (
    <Card 
      className={cn(
        'workflow-node trigger-node cursor-pointer transition-all duration-200 w-64 min-h-32',
        'hover:shadow-lg',
        selected && 'ring-2 ring-blue-500 shadow-lg',
        connecting && 'ring-2 ring-green-500 animate-pulse',
        readOnly && 'cursor-default'
      )}
      onClick={handleNodeClick}
    >
      {/* Output port only - triggers are start nodes */}
      <div className="absolute right-0 top-1/2 w-3 h-3 -mr-1.5 -mt-1.5">
        <div 
          className="w-full h-full rounded-full bg-green-400 hover:bg-green-500 cursor-pointer transition-colors"
          title="Output port"
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
              getTriggerColor(node.data.trigger_type)
            )}>
              <IconComponent className="h-4 w-4" />
            </div>
            
            <div>
              <h3 className="font-medium text-sm text-gray-900 truncate">
                {node.data.name}
              </h3>
              <p className="text-xs text-gray-500">
                Trigger
              </p>
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
        {/* Trigger Configuration */}
        {isEditing && (
          <div className="space-y-3">
            <div>
              <label className="text-xs font-medium text-gray-700 block mb-1">
                Trigger Type
              </label>
              <select
                value={node.data.trigger_type}
                onChange={(e) => handleTriggerTypeChange((e as React.ChangeEvent<HTMLSelectElement>).target.value as TriggerNodeData['trigger_type'])}
                className="w-full text-xs border border-gray-300 rounded px-2 py-1"
              >
                <option value="manual">Manual</option>
                <option value="webhook">Webhook</option>
                <option value="cron">Schedule (Cron)</option>
                <option value="event">Event</option>
                <option value="api">API Endpoint</option>
              </select>
            </div>

            <div>
              <label className="text-xs font-medium text-gray-700 block mb-1">
                Name
              </label>
              <Input
                value={node.data.name}
                onChange={(e) => handleConfigUpdate('name', (e as React.ChangeEvent<HTMLSelectElement>).target.value)}
                className="text-xs"
                placeholder="Trigger name..."
              />
            </div>

            {/* Webhook Configuration */}
            {node.data.trigger_type === 'webhook' && (
              <div className="space-y-2">
                <div>
                  <label className="text-xs font-medium text-gray-700 block mb-1">
                    HTTP Method
                  </label>
                  <select
                    value={node.data.config.method || 'POST'}
                    onChange={(e) => handleConfigUpdate('config', {...node.data.config, method: (e as React.ChangeEvent<HTMLSelectElement>).target.value})}
                    className="w-full text-xs border border-gray-300 rounded px-2 py-1"
                  >
                    <option value="POST">POST</option>
                    <option value="GET">GET</option>
                    <option value="PUT">PUT</option>
                    <option value="PATCH">PATCH</option>
                  </select>
                </div>
                
                <div>
                  <label className="text-xs font-medium text-gray-700 block mb-1">
                    Authentication
                  </label>
                  <select
                    value={node.data.config.authentication || 'none'}
                    onChange={(e) => handleConfigUpdate('config', {...node.data.config, authentication: (e as React.ChangeEvent<HTMLSelectElement>).target.value})}
                    className="w-full text-xs border border-gray-300 rounded px-2 py-1"
                  >
                    <option value="none">None</option>
                    <option value="token">Bearer Token</option>
                    <option value="signature">Signature</option>
                  </select>
                </div>
              </div>
            )}

            {/* Cron Configuration */}
            {node.data.trigger_type === 'cron' && (
              <div className="space-y-2">
                <div>
                  <label className="text-xs font-medium text-gray-700 block mb-1">
                    Schedule (Cron Expression)
                  </label>
                  <Input
                    value={node.data.config.schedule || '0 0 * * *'}
                    onChange={(e) => handleConfigUpdate('config', {...node.data.config, schedule: (e as React.ChangeEvent<HTMLSelectElement>).target.value})}
                    className="text-xs font-mono"
                    placeholder="0 0 * * *"
                  />
                  <p className="text-xs text-gray-500">
                    Daily at midnight UTC
                  </p>
                </div>
                
                <div>
                  <label className="text-xs font-medium text-gray-700 block mb-1">
                    Timezone
                  </label>
                  <Input
                    value={node.data.config.timezone || 'UTC'}
                    onChange={(e) => handleConfigUpdate('config', {...node.data.config, timezone: (e as React.ChangeEvent<HTMLSelectElement>).target.value})}
                    className="text-xs"
                    placeholder="UTC"
                  />
                </div>
              </div>
            )}

            {/* Event Configuration */}
            {node.data.trigger_type === 'event' && (
              <div className="space-y-2">
                <div>
                  <label className="text-xs font-medium text-gray-700 block mb-1">
                    Event Source
                  </label>
                  <Input
                    value={node.data.config.source || ''}
                    onChange={(e) => handleConfigUpdate('config', {...node.data.config, source: (e as React.ChangeEvent<HTMLSelectElement>).target.value})}
                    className="text-xs"
                    placeholder="event.source"
                  />
                </div>
              </div>
            )}

            {/* API Configuration */}
            {node.data.trigger_type === 'api' && (
              <div className="space-y-2">
                <div>
                  <label className="text-xs font-medium text-gray-700 block mb-1">
                    Endpoint Path
                  </label>
                  <Input
                    value={node.data.config.endpoint || ''}
                    onChange={(e) => handleConfigUpdate('config', {...node.data.config, endpoint: (e as React.ChangeEvent<HTMLSelectElement>).target.value})}
                    className="text-xs"
                    placeholder="/api/trigger"
                  />
                </div>
              </div>
            )}
          </div>
        )}

        {/* Trigger Info */}
        {!isEditing && (
          <div className="space-y-2">
            <p className="text-xs text-gray-600">
              {getTriggerDescription(node.data.trigger_type)}
            </p>

            {/* Show specific configuration */}
            {node.data.trigger_type === 'webhook' && node.data.webhook_url && (
              <div className="p-2 bg-purple-50 rounded text-xs">
                <p className="font-medium text-purple-700">Webhook URL:</p>
                <p className="text-purple-600 font-mono break-all">
                  {node.data.webhook_url}
                </p>
              </div>
            )}

            {node.data.trigger_type === 'cron' && node.data.config.schedule && (
              <div className="p-2 bg-orange-50 rounded text-xs">
                <p className="font-medium text-orange-700">Schedule:</p>
                <p className="text-orange-600 font-mono">
                  {node.data.config.schedule} ({node.data.config.timezone})
                </p>
              </div>
            )}

            {node.data.trigger_type === 'event' && node.data.config.source && (
              <div className="p-2 bg-green-50 rounded text-xs">
                <p className="font-medium text-green-700">Event Source:</p>
                <p className="text-green-600">
                  {node.data.config.source}
                </p>
              </div>
            )}
          </div>
        )}

        {/* Status */}
        <div className="flex justify-between items-center pt-2 border-t border-gray-200">
          <div className="flex items-center gap-1">
            <div className="w-2 h-2 rounded-full bg-green-400" />
            <span className="text-xs text-gray-500">Active</span>
          </div>
          
          <Badge 
            variant="secondary" 
            className={cn(
              'text-xs px-1 py-0',
              getTriggerColor(node.data.trigger_type)
            )}
          >
            {node.data.trigger_type}
          </Badge>
        </div>

        {/* Quick Actions for Manual Trigger */}
        {node.data.trigger_type === 'manual' && !readOnly && (
          <div className="pt-2">
            <Button 
              size="sm" 
              className="w-full text-xs"
              onClick={(e) => {
                e.stopPropagation();
                // Trigger manual execution
                console.log('Manual trigger activated:', node.id);
              }}
            >
              <Play className="h-3 w-3 mr-1" />
              Test Trigger
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}