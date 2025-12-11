'use client';

import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { EnhancedWorkflowCanvas } from '@/components/workflow/EnhancedWorkflowCanvas';
import { WorkflowChatInterface } from '@/components/workflow/WorkflowChatInterface';
import { WorkflowButtonInterface } from '@/components/workflow/WorkflowButtonInterface';
import { WorkflowFormInterface } from '@/components/workflow/WorkflowFormInterface';
import { WorkflowExecutionView } from '@/components/workflow/WorkflowExecutionView';
import { AppLayout } from '@/components/layout/app-layout';
import { AuthGuard } from '@/components/auth/auth-guard';
import { GT2_CAPABILITIES } from '@/lib/capabilities';
import { 
  Plus, 
  Search, 
  Filter,
  Play,
  Pause,
  Settings,
  MoreHorizontal,
  Bot,
  Zap,
  Clock,
  DollarSign,
  Activity,
  Edit,
  Copy,
  Trash2,
  Eye,
  MessageSquare,
  Square,
  BarChart3,
  Workflow
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface Workflow {
  id: string;
  name: string;
  description?: string;
  status: 'draft' | 'active' | 'paused' | 'archived';
  definition: {
    nodes: any[];
    edges: any[];
    config?: Record<string, any>;
  };
  interaction_modes: string[];
  execution_count: number;
  last_executed?: string;
  total_cost_cents: number;
  average_execution_time_ms?: number;
  created_at: string;
  updated_at: string;
}

interface WorkflowExecution {
  id: string;
  workflow_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  progress_percentage: number;
  started_at: string;
  completed_at?: string;
  tokens_used: number;
  cost_cents: number;
  interaction_mode: string;
}

function WorkflowsPageContent() {
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [executions, setExecutions] = useState<WorkflowExecution[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [viewMode, setViewMode] = useState<'list' | 'grid' | 'editor' | 'chat' | 'button' | 'form' | 'execution'>('list');
  const [selectedWorkflow, setSelectedWorkflow] = useState<Workflow | null>(null);
  const [selectedExecution, setSelectedExecution] = useState<WorkflowExecution | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);

  // Load workflows and executions
  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true);
        const authToken = localStorage.getItem('gt2_token');
        
        // Load workflows
        const workflowResponse = await fetch('/api/v1/workflows', {
          headers: {
            'Authorization': `Bearer ${authToken}`,
            'Content-Type': 'application/json'
          }
        });
        
        if (workflowResponse.ok) {
          const workflowData = await workflowResponse.json();
          setWorkflows(workflowData);
        }
        
        // Load recent executions for dashboard
        setExecutions([]); // TODO: Implement executions endpoint
        
      } catch (error) {
        console.error('Failed to load workflows:', error);
        setWorkflows([]);
        setExecutions([]);
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, []);

  // Filter workflows
  const filteredWorkflows = workflows.filter(workflow => {
    const matchesSearch = !searchQuery || 
      workflow.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      workflow.description?.toLowerCase().includes(searchQuery.toLowerCase());
    
    const matchesStatus = statusFilter === 'all' || workflow.status === statusFilter;
    
    return matchesSearch && matchesStatus;
  });

  // Execute workflow
  const handleExecuteWorkflow = async (workflow: Workflow, inputData: Record<string, any>) => {
    try {
      const authToken = localStorage.getItem('gt2_token');
      const response = await fetch(`/api/v1/workflows/${workflow.id}/execute`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          input_data: inputData,
          interaction_mode: viewMode,
          trigger_type: 'manual'
        })
      });

      if (response.ok) {
        const execution = await response.json();
        setSelectedExecution(execution);
        return execution;
      } else {
        throw new Error('Failed to execute workflow');
      }
    } catch (error) {
      console.error('Failed to execute workflow:', error);
      throw error;
    }
  };

  // Create new workflow
  const handleCreateWorkflow = async () => {
    try {
      const authToken = localStorage.getItem('gt2_token');
      const response = await fetch('/api/v1/workflows', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          name: 'New Workflow',
          description: 'A new workflow created with the visual editor',
          definition: {
            nodes: [
              {
                id: 'trigger-1',
                type: 'trigger',
                data: { name: 'Manual Trigger' },
                position: { x: 300, y: 200 }
              }
            ],
            edges: []
          },
          interaction_modes: ['button'],
          triggers: []
        })
      });

      if (response.ok) {
        const newWorkflow = await response.json();
        setWorkflows(prev => [newWorkflow, ...prev]);
        setSelectedWorkflow(newWorkflow);
        setViewMode('editor');
      } else {
        alert('Failed to create workflow. Please try again.');
      }
    } catch (error) {
      console.error('Failed to create workflow:', error);
      alert('Failed to create workflow. Please try again.');
    }
  };


  // Save workflow changes
  const handleSaveWorkflow = async (definition: any) => {
    if (!selectedWorkflow) return;
    
    try {
      const authToken = localStorage.getItem('gt2_token');
      const response = await fetch(`/api/v1/workflows/${selectedWorkflow.id}`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          definition: definition,
          status: 'active' // Activate workflow when saved
        })
      });

      if (response.ok) {
        const updatedWorkflow = await response.json();
        setWorkflows(prev => prev.map(w => 
          w.id === updatedWorkflow.id ? updatedWorkflow : w
        ));
        setSelectedWorkflow(updatedWorkflow);
        alert('Workflow saved successfully!');
      } else {
        alert('Failed to save workflow.');
      }
    } catch (error) {
      console.error('Failed to save workflow:', error);
      alert('Failed to save workflow.');
    }
  };

  // Delete workflow
  const handleDeleteWorkflow = async (workflowId: string) => {
    if (!confirm('Are you sure you want to delete this workflow?')) return;
    
    try {
      const authToken = localStorage.getItem('gt2_token');
      const response = await fetch(`/api/v1/workflows/${workflowId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        setWorkflows(prev => prev.filter(w => w.id !== workflowId));
        if (selectedWorkflow?.id === workflowId) {
          setSelectedWorkflow(null);
          setViewMode('list');
        }
      } else {
        alert('Failed to delete workflow.');
      }
    } catch (error) {
      console.error('Failed to delete workflow:', error);
      alert('Failed to delete workflow.');
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active': return 'bg-green-100 text-green-800';
      case 'draft': return 'bg-yellow-100 text-yellow-800';
      case 'paused': return 'bg-orange-100 text-orange-800';
      case 'archived': return 'bg-gray-100 text-gray-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  const getInteractionModeIcon = (mode: string) => {
    switch (mode) {
      case 'chat': return MessageSquare;
      case 'button': return Square;
      case 'form': return Edit;
      case 'dashboard': return BarChart3;
      default: return Square;
    }
  };

  // Calculate stats
  const totalWorkflows = workflows.length;
  const activeWorkflows = workflows.filter(w => w.status === 'active').length;
  const totalExecutions = workflows.reduce((sum, w) => sum + w.execution_count, 0);
  const totalCost = workflows.reduce((sum, w) => sum + w.total_cost_cents, 0);

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-2 border-gt-green border-t-transparent"></div>
      </div>
    );
  }

  // Interface views for different interaction modes
  if ((viewMode === 'chat' || viewMode === 'button' || viewMode === 'form') && selectedWorkflow) {
    const backToList = () => {
      setViewMode('list');
      setSelectedWorkflow(null);
    };

    const handleExecutionUpdate = (execution: WorkflowExecution) => {
      setSelectedExecution(execution);
      // Optionally switch to execution view to show results
      if (execution.status === 'completed' || execution.status === 'failed') {
        setViewMode('execution');
      }
    };

    return (
      <div className="min-h-screen bg-gray-50">
        {/* Interface Header */}
        <div className="bg-white border-b border-gray-200 p-4">
          <div className="max-w-4xl mx-auto flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Button variant="ghost" onClick={backToList}>
                ← Back to Workflows
              </Button>
              
              <div>
                <h1 className="text-xl font-bold text-gray-900">
                  {selectedWorkflow.name}
                </h1>
                <p className="text-gray-600 text-sm capitalize">
                  {viewMode} Interface
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <Badge className={getStatusColor(selectedWorkflow.status)}>
                {selectedWorkflow.status}
              </Badge>
              
              {/* Interface Mode Switcher */}
              <div className="flex bg-gray-100 rounded-lg p-1">
                {selectedWorkflow.interaction_modes.map(mode => (
                  <Button
                    key={mode}
                    variant={viewMode === mode ? 'primary' : 'ghost'}
                    size="sm"
                    onClick={() => setViewMode(mode as any)}
                    className="capitalize"
                  >
                    {mode}
                  </Button>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Interface Content */}
        <div className="max-w-4xl mx-auto p-6">
          {viewMode === 'chat' && (
            <WorkflowChatInterface
              workflow={selectedWorkflow as any}
              onExecute={(inputData) => handleExecuteWorkflow(selectedWorkflow, inputData)}
              onExecutionUpdate={handleExecutionUpdate}
            />
          )}
          
          {viewMode === 'button' && (
            <WorkflowButtonInterface
              workflow={selectedWorkflow as any}
              onExecute={(inputData) => handleExecuteWorkflow(selectedWorkflow, inputData)}
              onExecutionUpdate={handleExecutionUpdate}
              showDetailedStats={true}
            />
          )}
          
          {viewMode === 'form' && (
            <WorkflowFormInterface
              workflow={selectedWorkflow as any}
              onExecute={(inputData) => handleExecuteWorkflow(selectedWorkflow, inputData)}
              onExecutionUpdate={handleExecutionUpdate}
              multiStep={selectedWorkflow.definition.nodes.length > 3}
              showPreview={true}
            />
          )}
        </div>
      </div>
    );
  }

  // Execution view
  if (viewMode === 'execution' && selectedExecution) {
    return (
      <div className="min-h-screen bg-gray-50">
        {/* Execution Header */}
        <div className="bg-white border-b border-gray-200 p-4">
          <div className="max-w-6xl mx-auto flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Button 
                variant="ghost" 
                onClick={() => {
                  setViewMode('list');
                  setSelectedWorkflow(null);
                  setSelectedExecution(null);
                }}
              >
                ← Back to Workflows
              </Button>
              
              <div>
                <h1 className="text-xl font-bold text-gray-900">
                  Execution Details
                </h1>
                <p className="text-gray-600 text-sm">
                  {selectedWorkflow?.name || 'Workflow Execution'}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              {selectedWorkflow && (
                <Button 
                  variant="secondary"
                  onClick={() => {
                    setViewMode('button');
                    setSelectedExecution(null);
                  }}
                >
                  Run Again
                </Button>
              )}
            </div>
          </div>
        </div>

        {/* Execution Content */}
        <div className="max-w-6xl mx-auto p-6">
          <WorkflowExecutionView
            execution={selectedExecution as any}
            workflow={selectedWorkflow as any}
            onRerun={() => {
              setViewMode('button');
              setSelectedExecution(null);
            }}
            realtime={selectedExecution.status === 'running'}
          />
        </div>
      </div>
    );
  }

  // Editor view
  if (viewMode === 'editor' && selectedWorkflow) {
    return (
      <div className="h-screen flex flex-col">
        {/* Editor Header */}
        <div className="bg-white border-b border-gray-200 p-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Button 
              variant="ghost" 
              onClick={() => {
                setViewMode('list');
                setSelectedWorkflow(null);
              }}
            >
              ← Back to Workflows
            </Button>
            
            <div>
              <h1 className="text-xl font-bold text-gray-900">
                {selectedWorkflow.name}
              </h1>
              <p className="text-gray-600 text-sm">
                Visual Workflow Editor
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Badge className={getStatusColor(selectedWorkflow.status)}>
              {selectedWorkflow.status}
            </Badge>
            
            <Button 
              size="sm" 
              variant="secondary"
              onClick={() => handleExecuteWorkflow(selectedWorkflow, {})}
            >
              <Play className="h-4 w-4 mr-1" />
              Test Run
            </Button>
          </div>
        </div>

        {/* Enhanced Workflow Canvas */}
        <div className="flex-1">
          <EnhancedWorkflowCanvas
            workflow={selectedWorkflow}
            onSave={handleSaveWorkflow}
            onExecute={(definition) => handleExecuteWorkflow(selectedWorkflow, {})}
            onValidate={(definition) => {
              // Basic validation logic
              const errors: Array<{ nodeId?: string; edgeId?: string; message: string; type: 'error' | 'warning' }> = [];
              
              // Check for orphaned nodes
              const connectedNodes = new Set();
              definition.edges.forEach(edge => {
                connectedNodes.add(edge.source);
                connectedNodes.add(edge.target);
              });
              
              definition.nodes.forEach(node => {
                if (node.type !== 'trigger' && !connectedNodes.has(node.id)) {
                  errors.push({
                    nodeId: node.id,
                    message: 'Node is not connected to the workflow',
                    type: 'warning' as const
                  });
                }
                
                if (node.type === 'agent' && !node.data.agent_id && !node.data.agent_id) {
                  errors.push({
                    nodeId: node.id,
                    message: 'Agent node requires an agent to be selected',
                    type: 'error' as const
                  });
                }
              });
              
              return {
                isValid: errors.filter(e => e.type === 'error').length === 0,
                errors
              };
            }}
            autoSave={true}
            autoSaveInterval={3000}
          />
        </div>
      </div>
    );
  }

  // List/Grid view
  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="bg-white rounded-lg shadow-sm border p-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-3">
              <Workflow className="w-8 h-8 text-gt-green" />
              Workflows
            </h1>
            <p className="text-gray-600 mt-1">
              Create visual workflows using your AI Agents
            </p>
          </div>
          
          <div className="flex items-center gap-2">
            {/* View Mode Toggle */}
            <div className="flex bg-gray-100 rounded-lg p-1">
              <Button
                variant={viewMode === 'list' ? 'primary' : 'ghost'}
                size="sm"
                onClick={() => setViewMode('list')}
              >
                List
              </Button>
              <Button
                variant={viewMode === 'grid' ? 'primary' : 'ghost'}
                size="sm"
                onClick={() => setViewMode('grid')}
              >
                Grid
              </Button>
            </div>

            <Button onClick={handleCreateWorkflow} className="bg-gt-green hover:bg-gt-green/90">
              <Plus className="h-4 w-4 mr-2" />
              Create Workflow
            </Button>
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="flex-1 relative">
          <Search className="h-4 w-4 text-gray-400 absolute left-3 top-1/2 transform -translate-y-1/2" />
          <Input
            placeholder="Search workflows..."
            value={searchQuery}
            onChange={(value) => setSearchQuery(value)}
            className="pl-10"
          />
        </div>
        
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter((e as React.ChangeEvent<HTMLSelectElement>).target.value)}
          className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-gt-green focus:border-transparent"
        >
          <option value="all">All Status</option>
          <option value="active">Active</option>
          <option value="draft">Draft</option>
          <option value="paused">Paused</option>
          <option value="archived">Archived</option>
        </select>
      </div>

      {/* Workflows List/Grid */}
      {filteredWorkflows.length === 0 ? (
        <Card>
          <CardContent className="text-center py-12">
            <Bot className="h-12 w-12 text-gray-300 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">
              {searchQuery || statusFilter !== 'all' ? 'No workflows found' : 'No workflows yet'}
            </h3>
            <p className="text-gray-600 mb-4">
              {searchQuery || statusFilter !== 'all' 
                ? 'Try adjusting your search criteria'
                : 'Create your first visual workflow to get started'
              }
            </p>
            {!searchQuery && statusFilter === 'all' && (
              <Button onClick={handleCreateWorkflow}>
                <Plus className="h-4 w-4 mr-2" />
                Create Your First Workflow
              </Button>
            )}
          </CardContent>
        </Card>
      ) : (
        <div className={cn(
          viewMode === 'grid' 
            ? "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6"
            : "space-y-4"
        )}>
          {filteredWorkflows.map((workflow) => (
            <Card 
              key={workflow.id} 
              className="hover:shadow-lg transition-shadow duration-200 cursor-pointer"
              onClick={() => {
                setSelectedWorkflow(workflow);
                setViewMode('editor');
              }}
            >
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-purple-600 rounded-lg flex items-center justify-center">
                      <Bot className="h-5 w-5 text-white" />
                    </div>
                    
                    <div>
                      <h3 className="font-semibold text-gray-900 truncate">
                        {workflow.name}
                      </h3>
                      <div className="flex items-center gap-2 text-sm text-gray-500">
                        <span>{workflow.definition.nodes.length} nodes</span>
                        <span>•</span>
                        <span>{workflow.execution_count} runs</span>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <Badge className={getStatusColor(workflow.status)}>
                      {workflow.status}
                    </Badge>
                    
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => {
                        // Show actions menu
                      }}
                    >
                      <MoreHorizontal className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              </CardHeader>

              <CardContent className="space-y-3">
                {workflow.description && (
                  <p className="text-sm text-gray-600 line-clamp-2">
                    {workflow.description}
                  </p>
                )}

                {/* Interaction Modes */}
                <div className="flex flex-wrap gap-1">
                  {workflow.interaction_modes.map(mode => {
                    const Icon = getInteractionModeIcon(mode);
                    return (
                      <Badge 
                        key={mode} 
                        variant="secondary" 
                        className="text-xs px-2 py-1 cursor-pointer hover:bg-gray-100"
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedWorkflow(workflow);
                          setViewMode(mode as any);
                        }}
                      >
                        <Icon className="h-3 w-3 mr-1" />
                        {mode}
                      </Badge>
                    );
                  })}
                </div>

                {/* Stats */}
                <div className="grid grid-cols-3 gap-4 pt-3 border-t border-gray-200">
                  <div className="text-center">
                    <p className="text-xs text-gray-500">Executions</p>
                    <p className="font-semibold">{workflow.execution_count}</p>
                  </div>
                  
                  <div className="text-center">
                    <p className="text-xs text-gray-500">Avg. Time</p>
                    <p className="font-semibold">
                      {workflow.average_execution_time_ms ? 
                        `${Math.round(workflow.average_execution_time_ms / 1000)}s` : 
                        '-'
                      }
                    </p>
                  </div>
                  
                  <div className="text-center">
                    <p className="text-xs text-gray-500">Cost</p>
                    <p className="font-semibold">
                      ${(workflow.total_cost_cents / 100).toFixed(2)}
                    </p>
                  </div>
                </div>

                {/* Actions */}
                <div className="flex gap-2 pt-3">
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => {
                      setSelectedWorkflow(workflow);
                      // Use the first available interaction mode for quick run
                      const firstMode = workflow.interaction_modes[0] || 'button';
                      setViewMode(firstMode as any);
                    }}
                    className="flex-1"
                  >
                    <Play className="h-3 w-3 mr-1" />
                    Run
                  </Button>
                  
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => {
                      setSelectedWorkflow(workflow);
                      setViewMode('editor');
                    }}
                    className="flex-1"
                  >
                    <Edit className="h-3 w-3 mr-1" />
                    Edit
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

export default function WorkflowsPage() {
  return (
    <AuthGuard requiredCapabilities={[GT2_CAPABILITIES.AGENTS_EXECUTE]}>
      <AppLayout>
        <WorkflowsPageContent />
      </AppLayout>
    </AuthGuard>
  );
}