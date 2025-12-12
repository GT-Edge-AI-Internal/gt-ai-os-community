'use client';

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { Slider } from '@/components/ui/slider';
import { Badge } from '@/components/ui/badge';
import { 
  Bot, 
  Settings, 
  Circle,
  Square,
  Triangle,
  Hexagon,
  Zap
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface Agent {
  id: string;
  name: string;
  description: string;
  personality_type: 'geometric' | 'organic' | 'minimal' | 'technical';
  avatar_style?: 'circle' | 'square' | 'triangle' | 'hexagon';
  color_scheme?: string;
  capabilities: string[];
}

interface AgentNodeData {
  agent_id: string;       // Primary field
  agent_id?: string;  // Backward compatibility
  agent?: Agent;
  confidence_threshold: number;
  max_tokens: number;
  temperature: number;
  name: string;
}

interface WorkflowNode {
  id: string;
  type: string;
  position: { x: number; y: number };
  data: AgentNodeData;
  selected?: boolean;
}

interface AgentNodeProps {
  node: WorkflowNode;
  selected: boolean;
  connecting: boolean;
  onClick: () => void;
  onUpdate: (updates: Partial<WorkflowNode>) => void;
  onStartConnection: () => void;
  onFinishConnection: () => void;
  readOnly?: boolean;
}

export function AgentNode({
  node,
  selected,
  connecting,
  onClick,
  onUpdate,
  onStartConnection,
  onFinishConnection,
  readOnly = false
}: AgentNodeProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(false);

  // Load user's agents
  useEffect(() => {
    const loadAgents = async () => {
      try {
        setLoading(true);
        const authToken = localStorage.getItem('gt2_token');
        const response = await fetch('/api/v1/agents', {
          headers: {
            'Authorization': `Bearer ${authToken}`,
            'Content-Type': 'application/json'
          }
        });

        if (response.ok) {
          const data = await response.json();
          setAgents(data);
          
          // Auto-select agent if only one available
          if (data.length === 1 && !node.data.agent_id && !node.data.agent_id) {
            handleAgentSelect(data[0].id);
          }
        }
      } catch (error) {
        console.error('Failed to load agents:', error);
      } finally {
        setLoading(false);
      }
    };

    loadAgents();
  }, []);

  const selectedAgent = agents.find(a => a.id === (node.data.agent_id || node.data.agent_id));

  const handleAgentSelect = (agentId: string) => {
    const agent = agents.find(a => a.id === agentId);
    onUpdate({
      data: {
        ...node.data,
        agent_id: agentId,
        agent_id: agentId, // Backward compatibility
        agent: agent,
        name: agent ? `${agent.name} Agent` : 'AI Agent'
      }
    });
  };

  const handleConfigUpdate = (field: string, value: any) => {
    onUpdate({
      data: {
        ...node.data,
        [field]: value
      }
    });
  };

  const handleNodeClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (connecting) {
      onFinishConnection();
    } else {
      onClick();
    }
  };

  const getPersonalityIcon = (personality: string) => {
    switch (personality) {
      case 'geometric':
        return Square;
      case 'organic':
        return Circle;
      case 'minimal':
        return Triangle;
      case 'technical':
        return Hexagon;
      default:
        return Bot;
    }
  };

  const getPersonalityColor = (personality: string) => {
    switch (personality) {
      case 'geometric':
        return 'bg-blue-100 text-blue-700 border-blue-300';
      case 'organic':
        return 'bg-green-100 text-green-700 border-green-300';
      case 'minimal':
        return 'bg-gray-100 text-gray-700 border-gray-300';
      case 'technical':
        return 'bg-purple-100 text-purple-700 border-purple-300';
      default:
        return 'bg-gray-100 text-gray-600 border-gray-300';
    }
  };

  return (
    <Card 
      className={cn(
        'workflow-node agent-node cursor-pointer transition-all duration-200 w-64 min-h-32',
        'hover:shadow-lg',
        selected && 'ring-2 ring-blue-500 shadow-lg',
        connecting && 'ring-2 ring-green-500 animate-pulse',
        readOnly && 'cursor-default'
      )}
      onClick={handleNodeClick}
    >
      {/* Connection ports */}
      <div className="absolute left-0 top-1/2 w-3 h-3 -ml-1.5 -mt-1.5">
        <div 
          className="w-full h-full rounded-full bg-gray-400 hover:bg-blue-500 cursor-pointer transition-colors"
          title="Input port"
        />
      </div>
      
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
            {selectedAgent ? (
              <div className={cn(
                'w-8 h-8 rounded-full border-2 flex items-center justify-center',
                getPersonalityColor(selectedAgent.personality_type)
              )}>
                {React.createElement(getPersonalityIcon(selectedAgent.personality_type), {
                  className: 'h-4 w-4'
                })}
              </div>
            ) : (
              <Bot className="h-6 w-6 text-gray-400" />
            )}
            
            <div>
              <h3 className="font-medium text-sm text-gray-900 truncate">
                {selectedAgent?.name || node.data.name}
              </h3>
              <p className="text-xs text-gray-500">
                Agent Node
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
        {/* Agent Selection */}
        {isEditing && (
          <div className="space-y-3">
            <div>
              <label className="text-xs font-medium text-gray-700 block mb-1">
                Select Agent
              </label>
              {loading ? (
                <div className="text-xs text-gray-500">Loading agents...</div>
              ) : (
                <select
                  value={node.data.agent_id || node.data.agent_id || ''}
                  onChange={(e) => handleAgentSelect((e as React.ChangeEvent<HTMLSelectElement>).target.value)}
                  className="w-full text-xs border border-gray-300 rounded px-2 py-1"
                >
                  <option value="">Choose Agent...</option>
                  {agents.map(agent => (
                    <option key={agent.id} value={agent.id}>
                      {agent.name}
                    </option>
                  ))}
                </select>
              )}
            </div>

            {/* Configuration */}
            <div>
              <label className="text-xs font-medium text-gray-700 block mb-1">
                Confidence Threshold: {node.data.confidence_threshold}%
              </label>
              <Slider
                value={[node.data.confidence_threshold]}
                onValueChange={(value) => handleConfigUpdate('confidence_threshold', value[0])}
                min={0}
                max={100}
                step={5}
                className="w-full"
              />
            </div>

            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-xs font-medium text-gray-700 block mb-1">
                  Max Tokens
                </label>
                <Input
                  type="number"
                  value={node.data.max_tokens}
                  onChange={(e) => handleConfigUpdate('max_tokens', parseInt((e as React.ChangeEvent<HTMLSelectElement>).target.value))}
                  min={100}
                  max={8000}
                  className="text-xs"
                />
              </div>
              
              <div>
                <label className="text-xs font-medium text-gray-700 block mb-1">
                  Temperature
                </label>
                <Input
                  type="number"
                  value={node.data.temperature}
                  onChange={(e) => handleConfigUpdate('temperature', parseFloat((e as React.ChangeEvent<HTMLSelectElement>).target.value))}
                  min={0}
                  max={2}
                  step={0.1}
                  className="text-xs"
                />
              </div>
            </div>
          </div>
        )}

        {/* Agent Info */}
        {selectedAgent && !isEditing && (
          <div className="space-y-2">
            <p className="text-xs text-gray-600 line-clamp-2">
              {selectedAgent.description}
            </p>
            
            <div className="flex flex-wrap gap-1">
              {selectedAgent.capabilities.slice(0, 3).map((capability, index) => (
                <Badge key={index} variant="secondary" className="text-xs px-1 py-0">
                  {capability}
                </Badge>
              ))}
              {selectedAgent.capabilities.length > 3 && (
                <Badge variant="secondary" className="text-xs px-1 py-0">
                  +{selectedAgent.capabilities.length - 3}
                </Badge>
              )}
            </div>

            <div className="flex items-center justify-between text-xs text-gray-500">
              <span>Confidence: {node.data.confidence_threshold}%</span>
              <div className="flex items-center gap-1">
                <Zap className="h-3 w-3" />
                <span>{node.data.max_tokens} tokens</span>
              </div>
            </div>
          </div>
        )}

        {/* Empty State */}
        {!selectedAgent && !isEditing && (
          <div className="text-center py-4">
            <Bot className="h-8 w-8 text-gray-300 mx-auto mb-2" />
            <p className="text-xs text-gray-500">
              No agent selected
            </p>
            <Button
              size="sm"
              variant="secondary"
              className="mt-2 text-xs"
              onClick={(e) => {
                e.stopPropagation();
                setIsEditing(true);
              }}
            >
              Configure
            </Button>
          </div>
        )}

        {/* Status Indicators */}
        <div className="flex justify-between items-center pt-2 border-t border-gray-200">
          <div className="flex items-center gap-1">
            <div className={cn(
              'w-2 h-2 rounded-full',
              selectedAgent ? 'bg-green-400' : 'bg-gray-300'
            )} />
            <span className="text-xs text-gray-500">
              {selectedAgent ? 'Ready' : 'Not configured'}
            </span>
          </div>
          
          {selectedAgent && (
            <Badge 
              variant="secondary" 
              className={cn(
                'text-xs px-1 py-0',
                getPersonalityColor(selectedAgent.personality_type)
              )}
            >
              {selectedAgent.personality_type}
            </Badge>
          )}
        </div>
      </CardContent>
    </Card>
  );
}