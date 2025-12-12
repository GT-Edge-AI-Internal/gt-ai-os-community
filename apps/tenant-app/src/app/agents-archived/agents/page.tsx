'use client';

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { AgentCard } from '@/components/agents/agent-card';
import { AgentCreateModal } from '@/components/agents';
import { AgentExecutionModal } from '@/components/agents/agent-execution-modal';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import {
  Plus,
  Search,
  Filter,
  Bot,
  Brain,
  Code,
  Activity,
  Clock,
  DollarSign,
  TrendingUp,
  Zap
} from 'lucide-react';

interface Agent {
  id: string;
  name: string;
  description?: string;
  agent_type: 'research' | 'coding' | 'analysis' | 'custom';
  capabilities: string[];
  usage_count: number;
  last_used?: string;
  is_active: boolean;
  created_at: string;
}

interface AgentExecution {
  id: string;
  agent_id: string;
  task_description: string;
  task_parameters: Record<string, any>;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  progress_percentage: number;
  current_step?: string;
  result_data: Record<string, any>;
  output_artifacts: string[];
  error_details?: string;
  execution_time_ms?: number;
  tokens_used: number;
  cost_cents: number;
  tool_calls_count: number;
  started_at?: string;
  completed_at?: string;
  created_at: string;
}

import { AppLayout } from '@/components/layout/app-layout';

function AgentsPageContent() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [executions, setExecutions] = useState<AgentExecution[]>([]);
  const [filteredAgents, setFilteredAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedType, setSelectedType] = useState<string>('all');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showExecuteModal, setShowExecuteModal] = useState(false);
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null);
  const [currentExecution, setCurrentExecution] = useState<AgentExecution | null>(null);

  // Load real data from backend API
  useEffect(() => {
    const loadAgents = async () => {
      try {
        setLoading(true);
        
        // Load agents from backend API - using standardized GT 2.0 token key
        const authToken = localStorage.getItem('gt2_token');
        const response = await fetch('http://localhost:8001/api/v1/agents', {
          headers: {
            'Authorization': `Bearer ${authToken}`,
            'Content-Type': 'application/json'
          }
        });
        
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const backendAgents = await response.json();
        
        // Convert backend format to frontend format
        const convertedAgents: Agent[] = backendAgents.map((agent: any) => ({
          id: agent.id,
          name: agent.name,
          description: agent.description,
          agent_type: agent.agent_type,
          capabilities: agent.capabilities || [],
          usage_count: agent.usage_count || 0,
          last_used: agent.last_used,
          is_active: agent.is_active,
          created_at: agent.created_at
        }));
        
        setAgents(convertedAgents);
        setFilteredAgents(convertedAgents);
        
        // Load recent executions
        // TODO: Add execution history endpoint to backend
        setExecutions([]);
        
      } catch (error) {
        console.error('Failed to load agents:', error);
        // Fallback to empty state instead of mock data
        setAgents([]);
        setFilteredAgents([]);
        setExecutions([]);
      } finally {
        setLoading(false);
      }
    };

    loadAgents();
  }, []);

  // Filter agents based on search and type
  useEffect(() => {
    let filtered = agents;

    if (searchQuery) {
      filtered = filtered.filter(agent =>
        agent.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        agent.description?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        agent.capabilities.some(cap => cap.toLowerCase().includes(searchQuery.toLowerCase()))
      );
    }

    if (selectedType !== 'all') {
      filtered = filtered.filter(agent => agent.agent_type === selectedType);
    }

    setFilteredAgents(filtered);
  }, [agents, searchQuery, selectedType]);

  const handleCreateAgent = async (agentData: any) => {
    try {
      const authToken = localStorage.getItem('gt2_token');
      const response = await fetch('http://localhost:8001/api/v1/agents', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          name: agentData.name,
          description: agentData.description,
          agent_type: agentData.agent_type,
          prompt_template: agentData.prompt_template || `You are a ${agentData.agent_type} agent focused on helping users with ${agentData.description || 'various tasks'}.`,
          capabilities: agentData.capabilities || [],
          model_preferences: agentData.model_preferences || {},
          personality_config: agentData.personality_config || {},
          memory_type: agentData.memory_type || 'conversation',
          available_tools: agentData.available_tools || [],
          resource_bindings: agentData.resource_bindings || []
        })
      });
      
      if (!response.ok) {
        throw new Error(`Failed to create agent: ${response.status}`);
      }
      
      const newAgent = await response.json();
      
      // Convert to frontend format and add to state
      const convertedAgent: Agent = {
        id: newAgent.id,
        name: newAgent.name,
        description: newAgent.description,
        agent_type: newAgent.agent_type,
        capabilities: newAgent.capabilities || [],
        usage_count: newAgent.usage_count || 0,
        last_used: newAgent.last_used,
        is_active: newAgent.is_active,
        created_at: newAgent.created_at
      };

      setAgents(prev => [convertedAgent, ...prev]);
      setShowCreateModal(false);
    } catch (error) {
      console.error('Failed to create agent:', error);
      alert('Failed to create agent. Please try again.');
    }
  };

  const handleExecuteAgent = async (agentId: string, taskDescription: string, parameters: Record<string, any>) => {
    try {
      const authToken = localStorage.getItem('gt2_token');
      const response = await fetch(`http://localhost:8001/api/v1/agents/${agentId}/execute`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          task_description: taskDescription,
          task_parameters: parameters,
          execution_context: {}
        })
      });
      
      if (!response.ok) {
        throw new Error(`Failed to execute agent: ${response.status}`);
      }
      
      const execution = await response.json();
      
      // Convert to frontend format
      const convertedExecution: AgentExecution = {
        id: execution.id,
        agent_id: execution.agent_id,
        task_description: execution.task_description,
        task_parameters: execution.task_parameters || {},
        status: execution.status,
        progress_percentage: execution.progress_percentage || 0,
        current_step: execution.current_step,
        result_data: execution.result_data || {},
        output_artifacts: execution.output_artifacts || [],
        tokens_used: execution.tokens_used || 0,
        cost_cents: execution.cost_cents || 0,
        tool_calls_count: execution.tool_calls_count || 0,
        started_at: execution.started_at,
        completed_at: execution.completed_at,
        created_at: execution.created_at
      };

      setCurrentExecution(convertedExecution);
      setExecutions(prev => [convertedExecution, ...prev]);

      // Poll for updates if execution is running
      if (convertedExecution.status === 'running' || convertedExecution.status === 'pending') {
        const pollExecution = async () => {
          try {
            const statusResponse = await fetch(`http://localhost:8001/api/v1/agents/executions/${execution.id}`, {
              headers: {
                'Authorization': `Bearer ${authToken}`
              }
            });
            
            if (statusResponse.ok) {
              const updatedExecution = await statusResponse.json();
              const convertedUpdate: AgentExecution = {
                id: updatedExecution.id,
                agent_id: updatedExecution.agent_id,
                task_description: updatedExecution.task_description,
                task_parameters: updatedExecution.task_parameters || {},
                status: updatedExecution.status,
                progress_percentage: updatedExecution.progress_percentage || 0,
                current_step: updatedExecution.current_step,
                result_data: updatedExecution.result_data || {},
                output_artifacts: updatedExecution.output_artifacts || [],
                tokens_used: updatedExecution.tokens_used || 0,
                cost_cents: updatedExecution.cost_cents || 0,
                tool_calls_count: updatedExecution.tool_calls_count || 0,
                started_at: updatedExecution.started_at,
                completed_at: updatedExecution.completed_at,
                created_at: updatedExecution.created_at
              };
              
              setCurrentExecution(convertedUpdate);
              
              // Continue polling if still running
              if (convertedUpdate.status === 'running' || convertedUpdate.status === 'pending') {
                setTimeout(pollExecution, 2000);
              }
            }
          } catch (pollError) {
            console.error('Error polling execution status:', pollError);
          }
        };
        
        // Start polling after 2 seconds
        setTimeout(pollExecution, 2000);
      }

    } catch (error) {
      console.error('Failed to execute agent:', error);
      alert('Failed to execute agent. Please try again.');
    }
  };

  const handleEditAgent = (agent: Agent) => {
    // TODO: Implement edit functionality
    console.log('Edit agent:', agent);
  };

  const handleDeleteAgent = async (agentId: string) => {
    try {
      const authToken = localStorage.getItem('gt2_token');
      const response = await fetch(`http://localhost:8001/api/v1/agents/${agentId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Content-Type': 'application/json'
        }
      });
      
      if (!response.ok) {
        throw new Error(`Failed to delete agent: ${response.status}`);
      }
      
      setAgents(prev => prev.filter(agent => agent.id !== agentId));
    } catch (error) {
      console.error('Failed to delete agent:', error);
      alert('Failed to delete agent. Please try again.');
    }
  };

  const handleCloneAgent = (agent: Agent) => {
    // TODO: Implement clone functionality
    console.log('Clone agent:', agent);
  };

  const openExecuteModal = (agentId: string) => {
    const agent = agents.find(a => a.id === agentId);
    setSelectedAgent(agent || null);
    setCurrentExecution(null);
    setShowExecuteModal(true);
  };

  // Calculate stats
  const totalAgents = agents.length;
  const activeAgents = agents.filter(a => a.is_active).length;
  const totalExecutions = executions.length;
  const totalTokensUsed = executions.reduce((sum, exec) => sum + exec.tokens_used, 0);
  const totalCost = executions.reduce((sum, exec) => sum + exec.cost_cents, 0);

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-2 border-gt-green border-t-transparent"></div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">AI Agents</h1>
          <p className="text-gray-600">Create and manage AI agents for automated tasks</p>
        </div>
        <Button onClick={() => setShowCreateModal(true)}>
          <Plus className="h-4 w-4 mr-2" />
          Create Agent
        </Button>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center space-x-2">
              <Bot className="h-4 w-4 text-blue-600" />
              <div>
                <p className="text-sm text-gray-600">Total Agents</p>
                <p className="text-xl font-semibold">{totalAgents}</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center space-x-2">
              <Zap className="h-4 w-4 text-green-600" />
              <div>
                <p className="text-sm text-gray-600">Active</p>
                <p className="text-xl font-semibold">{activeAgents}</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center space-x-2">
              <Activity className="h-4 w-4 text-purple-600" />
              <div>
                <p className="text-sm text-gray-600">Executions</p>
                <p className="text-xl font-semibold">{totalExecutions}</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center space-x-2">
              <Brain className="h-4 w-4 text-orange-600" />
              <div>
                <p className="text-sm text-gray-600">Tokens Used</p>
                <p className="text-xl font-semibold">{totalTokensUsed.toLocaleString()}</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center space-x-2">
              <DollarSign className="h-4 w-4 text-green-600" />
              <div>
                <p className="text-sm text-gray-600">Total Cost</p>
                <p className="text-xl font-semibold">${(totalCost / 100).toFixed(2)}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="flex-1 relative">
          <Search className="h-4 w-4 text-gray-400 absolute left-3 top-1/2 transform -translate-y-1/2" />
          <Input
            placeholder="Search agents..."
            value={searchQuery}
            onChange={(e: any) => setSearchQuery(e.target.value)}
            className="pl-10"
          />
        </div>
        
        <select
          value={selectedType}
          onChange={(e) => setSelectedType((e as React.ChangeEvent<HTMLSelectElement>).target.value)}
          className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-gt-green focus:border-transparent"
        >
          <option value="all">All Types</option>
          <option value="research">Research</option>
          <option value="coding">Coding</option>
          <option value="analysis">Analysis</option>
          <option value="custom">Custom</option>
        </select>
      </div>

      {/* Agents Grid */}
      {filteredAgents.length === 0 ? (
        <Card>
          <CardContent className="text-center py-12">
            <Bot className="h-12 w-12 text-gray-300 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">
              {searchQuery || selectedType !== 'all' ? 'No agents found' : 'No agents yet'}
            </h3>
            <p className="text-gray-600 mb-4">
              {searchQuery || selectedType !== 'all' 
                ? 'Try adjusting your search criteria'
                : 'Create your first AI agent to get started'
              }
            </p>
            {!searchQuery && selectedType === 'all' && (
              <Button onClick={() => setShowCreateModal(true)}>
                <Plus className="h-4 w-4 mr-2" />
                Create Your First Agent
              </Button>
            )}
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredAgents.map((agent) => (
            <AgentCard
              key={agent.id}
              agent={agent}
              onExecute={openExecuteModal}
              onEdit={handleEditAgent}
              onDelete={handleDeleteAgent}
              onClone={handleCloneAgent}
            />
          ))}
        </div>
      )}

      {/* Create Agent Modal */}
      <AgentCreateModal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        onSubmit={handleCreateAgent}
      />

      {/* Execute Agent Modal */}
      <AgentExecutionModal
        isOpen={showExecuteModal}
        onClose={() => {
          setShowExecuteModal(false);
          setSelectedAgent(null);
          setCurrentExecution(null);
        }}
        agent={selectedAgent}
        onExecute={handleExecuteAgent}
        execution={currentExecution}
      />
    </div>
  );
}

export default function AgentsPage() {
  return (
    <AppLayout>
      <AgentsPageContent />
    </AppLayout>
  );
}