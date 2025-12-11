'use client';

import React, { useState } from 'react';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { 
  Settings, 
  Globe, 
  Database, 
  HardDrive, 
  Webhook,
  Key,
  Link
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface IntegrationNodeData {
  integration_type: 'api' | 'database' | 'storage' | 'webhook' | 'mcp';
  name: string;
  config: Record<string, any>;
  api_key_id?: string;
  endpoint_url?: string;
  method?: string;
}

interface WorkflowNode {
  id: string;
  type: string;
  position: { x: number; y: number };
  data: IntegrationNodeData;
  selected?: boolean;
}

interface IntegrationNodeProps {
  node: WorkflowNode;
  selected: boolean;
  connecting: boolean;
  onClick: () => void;
  onUpdate: (updates: Partial<WorkflowNode>) => void;
  onStartConnection: () => void;
  onFinishConnection: () => void;
  readOnly?: boolean;
}

export function IntegrationNode({
  node,
  selected,
  connecting,
  onClick,
  onUpdate,
  onStartConnection,
  onFinishConnection,
  readOnly = false
}: IntegrationNodeProps) {
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

  const handleIntegrationTypeChange = (integrationType: IntegrationNodeData['integration_type']) => {
    const defaultConfigs = {
      api: { method: 'GET', headers: {}, timeout: 30 },
      database: { query: '', connection_type: 'read' },
      storage: { operation: 'read', bucket: '', path: '' },
      webhook: { method: 'POST', url: '', headers: {} },
      mcp: { server: '', function: '', parameters: {} }
    };

    onUpdate({
      data: {
        ...node.data,
        integration_type: integrationType,
        config: defaultConfigs[integrationType],
        name: `${integrationType.toUpperCase()} Integration`
      }
    });
  };

  const getIntegrationIcon = (integrationType: string) => {
    switch (integrationType) {
      case 'api':
        return Globe;
      case 'database':
        return Database;
      case 'storage':
        return HardDrive;
      case 'webhook':
        return Webhook;
      case 'mcp':
        return Link;
      default:
        return Globe;
    }
  };

  const getIntegrationColor = (integrationType: string) => {
    switch (integrationType) {
      case 'api':
        return 'bg-blue-100 text-blue-700 border-blue-300';
      case 'database':
        return 'bg-green-100 text-green-700 border-green-300';
      case 'storage':
        return 'bg-orange-100 text-orange-700 border-orange-300';
      case 'webhook':
        return 'bg-purple-100 text-purple-700 border-purple-300';
      case 'mcp':
        return 'bg-red-100 text-red-700 border-red-300';
      default:
        return 'bg-gray-100 text-gray-600 border-gray-300';
    }
  };

  const getIntegrationDescription = (integrationType: string) => {
    switch (integrationType) {
      case 'api':
        return 'HTTP/REST API call';
      case 'database':
        return 'Database query/operation';
      case 'storage':
        return 'File storage operation';
      case 'webhook':
        return 'Outbound webhook call';
      case 'mcp':
        return 'MCP server function';
      default:
        return 'External integration';
    }
  };

  const IconComponent = getIntegrationIcon(node.data.integration_type);

  return (
    <Card 
      className={cn(
        'workflow-node integration-node cursor-pointer transition-all duration-200 w-64 min-h-32',
        'hover:shadow-lg',
        selected && 'ring-2 ring-blue-500 shadow-lg',
        connecting && 'ring-2 ring-green-500 animate-pulse',
        readOnly && 'cursor-default'
      )}
      onClick={handleNodeClick}
    >
      {/* Input port */}
      <div className="absolute left-0 top-1/2 w-3 h-3 -ml-1.5 -mt-1.5">
        <div 
          className="w-full h-full rounded-full bg-gray-400 hover:bg-blue-500 cursor-pointer transition-colors"
          title="Input port"
        />
      </div>
      
      {/* Output port */}
      <div className="absolute right-0 top-1/2 w-3 h-3 -mr-1.5 -mt-1.5">
        <div 
          className="w-full h-full rounded-full bg-gray-400 hover:bg-blue-500 cursor-pointer transition-colors"
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
              getIntegrationColor(node.data.integration_type)
            )}>
              <IconComponent className="h-4 w-4" />
            </div>
            
            <div>
              <h3 className="font-medium text-sm text-gray-900 truncate">
                {node.data.name}
              </h3>
              <p className="text-xs text-gray-500">
                Integration
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
        {/* Integration Configuration */}
        {isEditing && (
          <div className="space-y-3">
            <div>
              <label className="text-xs font-medium text-gray-700 block mb-1">
                Integration Type
              </label>
              <select
                value={node.data.integration_type}
                onChange={(e) => handleIntegrationTypeChange((e as React.ChangeEvent<HTMLSelectElement>).target.value as IntegrationNodeData['integration_type'])}
                className="w-full text-xs border border-gray-300 rounded px-2 py-1"
              >
                <option value="api">API Call</option>
                <option value="database">Database</option>
                <option value="storage">Storage</option>
                <option value="webhook">Webhook</option>
                <option value="mcp">MCP Server</option>
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
                placeholder="Integration name..."
              />
            </div>

            {/* API Configuration */}
            {node.data.integration_type === 'api' && (
              <div className="space-y-2">
                <div>
                  <label className="text-xs font-medium text-gray-700 block mb-1">
                    URL
                  </label>
                  <Input
                    value={node.data.endpoint_url || ''}
                    onChange={(e) => handleConfigUpdate('endpoint_url', (e as React.ChangeEvent<HTMLSelectElement>).target.value)}
                    className="text-xs"
                    placeholder="https://api.example.com/endpoint"
                  />
                </div>
                
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="text-xs font-medium text-gray-700 block mb-1">
                      Method
                    </label>
                    <select
                      value={node.data.config.method || 'GET'}
                      onChange={(e) => handleConfigUpdate('config', {...node.data.config, method: (e as React.ChangeEvent<HTMLSelectElement>).target.value})}
                      className="w-full text-xs border border-gray-300 rounded px-2 py-1"
                    >
                      <option value="GET">GET</option>
                      <option value="POST">POST</option>
                      <option value="PUT">PUT</option>
                      <option value="DELETE">DELETE</option>
                      <option value="PATCH">PATCH</option>
                    </select>
                  </div>
                  
                  <div>
                    <label className="text-xs font-medium text-gray-700 block mb-1">
                      Timeout (s)
                    </label>
                    <Input
                      type="number"
                      value={node.data.config.timeout || 30}
                      onChange={(e) => handleConfigUpdate('config', {...node.data.config, timeout: parseInt((e as React.ChangeEvent<HTMLSelectElement>).target.value)})}
                      className="text-xs"
                      min={5}
                      max={300}
                    />
                  </div>
                </div>

                <div>
                  <label className="text-xs font-medium text-gray-700 block mb-1">
                    API Key
                  </label>
                  <select
                    value={node.data.api_key_id || ''}
                    onChange={(e) => handleConfigUpdate('api_key_id', (e as React.ChangeEvent<HTMLSelectElement>).target.value)}
                    className="w-full text-xs border border-gray-300 rounded px-2 py-1"
                  >
                    <option value="">No authentication</option>
                    <option value="key1">API Key 1</option>
                    <option value="key2">API Key 2</option>
                  </select>
                </div>
              </div>
            )}

            {/* Database Configuration */}
            {node.data.integration_type === 'database' && (
              <div className="space-y-2">
                <div>
                  <label className="text-xs font-medium text-gray-700 block mb-1">
                    Connection Type
                  </label>
                  <select
                    value={node.data.config.connection_type || 'read'}
                    onChange={(e) => handleConfigUpdate('config', {...node.data.config, connection_type: (e as React.ChangeEvent<HTMLSelectElement>).target.value})}
                    className="w-full text-xs border border-gray-300 rounded px-2 py-1"
                  >
                    <option value="read">Read Only</option>
                    <option value="write">Write</option>
                    <option value="readwrite">Read/Write</option>
                  </select>
                </div>
                
                <div>
                  <label className="text-xs font-medium text-gray-700 block mb-1">
                    Query/Operation
                  </label>
                  <textarea
                    value={node.data.config.query || ''}
                    onChange={(e) => handleConfigUpdate('config', {...node.data.config, query: (e as React.ChangeEvent<HTMLSelectElement>).target.value})}
                    className="w-full text-xs border border-gray-300 rounded px-2 py-1 font-mono"
                    placeholder="SELECT * FROM table WHERE..."
                    rows={3}
                  />
                </div>
              </div>
            )}

            {/* Storage Configuration */}
            {node.data.integration_type === 'storage' && (
              <div className="space-y-2">
                <div>
                  <label className="text-xs font-medium text-gray-700 block mb-1">
                    Operation
                  </label>
                  <select
                    value={node.data.config.operation || 'read'}
                    onChange={(e) => handleConfigUpdate('config', {...node.data.config, operation: (e as React.ChangeEvent<HTMLSelectElement>).target.value})}
                    className="w-full text-xs border border-gray-300 rounded px-2 py-1"
                  >
                    <option value="read">Read File</option>
                    <option value="write">Write File</option>
                    <option value="delete">Delete File</option>
                    <option value="list">List Files</option>
                  </select>
                </div>
                
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="text-xs font-medium text-gray-700 block mb-1">
                      Bucket
                    </label>
                    <Input
                      value={node.data.config.bucket || ''}
                      onChange={(e) => handleConfigUpdate('config', {...node.data.config, bucket: (e as React.ChangeEvent<HTMLSelectElement>).target.value})}
                      className="text-xs"
                      placeholder="bucket-name"
                    />
                  </div>
                  
                  <div>
                    <label className="text-xs font-medium text-gray-700 block mb-1">
                      Path
                    </label>
                    <Input
                      value={node.data.config.path || ''}
                      onChange={(e) => handleConfigUpdate('config', {...node.data.config, path: (e as React.ChangeEvent<HTMLSelectElement>).target.value})}
                      className="text-xs"
                      placeholder="/path/to/file"
                    />
                  </div>
                </div>
              </div>
            )}

            {/* Webhook Configuration */}
            {node.data.integration_type === 'webhook' && (
              <div className="space-y-2">
                <div>
                  <label className="text-xs font-medium text-gray-700 block mb-1">
                    Webhook URL
                  </label>
                  <Input
                    value={node.data.config.url || ''}
                    onChange={(e) => handleConfigUpdate('config', {...node.data.config, url: (e as React.ChangeEvent<HTMLSelectElement>).target.value})}
                    className="text-xs"
                    placeholder="https://webhook.example.com/endpoint"
                  />
                </div>
                
                <div>
                  <label className="text-xs font-medium text-gray-700 block mb-1">
                    Method
                  </label>
                  <select
                    value={node.data.config.method || 'POST'}
                    onChange={(e) => handleConfigUpdate('config', {...node.data.config, method: (e as React.ChangeEvent<HTMLSelectElement>).target.value})}
                    className="w-full text-xs border border-gray-300 rounded px-2 py-1"
                  >
                    <option value="POST">POST</option>
                    <option value="PUT">PUT</option>
                    <option value="PATCH">PATCH</option>
                  </select>
                </div>
              </div>
            )}

            {/* MCP Configuration */}
            {node.data.integration_type === 'mcp' && (
              <div className="space-y-2">
                <div>
                  <label className="text-xs font-medium text-gray-700 block mb-1">
                    MCP Server
                  </label>
                  <select
                    value={node.data.config.server || ''}
                    onChange={(e) => handleConfigUpdate('config', {...node.data.config, server: (e as React.ChangeEvent<HTMLSelectElement>).target.value})}
                    className="w-full text-xs border border-gray-300 rounded px-2 py-1"
                  >
                    <option value="">Select server...</option>
                    <option value="github">GitHub</option>
                    <option value="slack">Slack</option>
                    <option value="database">Database</option>
                  </select>
                </div>
                
                <div>
                  <label className="text-xs font-medium text-gray-700 block mb-1">
                    Function
                  </label>
                  <Input
                    value={node.data.config.function || ''}
                    onChange={(e) => handleConfigUpdate('config', {...node.data.config, function: (e as React.ChangeEvent<HTMLSelectElement>).target.value})}
                    className="text-xs"
                    placeholder="function_name"
                  />
                </div>
              </div>
            )}
          </div>
        )}

        {/* Integration Info */}
        {!isEditing && (
          <div className="space-y-2">
            <p className="text-xs text-gray-600">
              {getIntegrationDescription(node.data.integration_type)}
            </p>

            {/* Show specific configuration */}
            {node.data.endpoint_url && (
              <div className="p-2 bg-blue-50 rounded text-xs">
                <p className="font-medium text-blue-700">Endpoint:</p>
                <p className="text-blue-600 break-all">
                  {node.data.method || 'GET'} {node.data.endpoint_url}
                </p>
              </div>
            )}

            {node.data.integration_type === 'database' && node.data.config.query && (
              <div className="p-2 bg-green-50 rounded text-xs">
                <p className="font-medium text-green-700">Query:</p>
                <p className="text-green-600 font-mono text-xs break-all">
                  {node.data.config.query}
                </p>
              </div>
            )}

            {node.data.integration_type === 'storage' && (
              <div className="p-2 bg-orange-50 rounded text-xs">
                <p className="font-medium text-orange-700">Storage:</p>
                <p className="text-orange-600">
                  {node.data.config.operation} {node.data.config.bucket}/{node.data.config.path}
                </p>
              </div>
            )}
          </div>
        )}

        {/* Status */}
        <div className="flex justify-between items-center pt-2 border-t border-gray-200">
          <div className="flex items-center gap-1">
            <div className={cn(
              'w-2 h-2 rounded-full',
              (node.data.endpoint_url || node.data.config.url || node.data.config.server) ? 'bg-green-400' : 'bg-yellow-400'
            )} />
            <span className="text-xs text-gray-500">
              {(node.data.endpoint_url || node.data.config.url || node.data.config.server) ? 'Configured' : 'Needs config'}
            </span>
          </div>
          
          <div className="flex items-center gap-1">
            {node.data.api_key_id && (
              <Badge variant="secondary" className="text-xs px-1 py-0 bg-yellow-50 text-yellow-700">
                <Key className="h-2 w-2 mr-1" />
                Auth
              </Badge>
            )}
            
            <Badge 
              variant="secondary" 
              className={cn(
                'text-xs px-1 py-0',
                getIntegrationColor(node.data.integration_type)
              )}
            >
              {node.data.integration_type}
            </Badge>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}