'use client';

import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Separator } from '@/components/ui/separator';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { 
  Play, Square, RotateCcw, FileText, Clock, Zap, DollarSign, 
  Activity, AlertTriangle, CheckCircle, Info, Eye, EyeOff,
  Settings, Code, Database, Network, Bot, Target, Send,
  Download, Upload, Share, Copy, Trash2, Edit, Plus
} from 'lucide-react';
import { cn, formatDateTime } from '@/lib/utils';
import { 
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';

interface TestScenario {
  id: string;
  name: string;
  description?: string;
  inputData: Record<string, any>;
  expectedOutputs?: Record<string, any>;
  tags?: string[];
  createdAt: string;
}

interface TestExecution {
  id: string;
  scenarioId: string;
  workflowId: string;
  status: 'running' | 'completed' | 'failed' | 'cancelled';
  startedAt: string;
  completedAt?: string;
  duration?: number;
  inputData: Record<string, any>;
  outputData?: Record<string, any>;
  nodeExecutions: Array<{
    nodeId: string;
    nodeType: string;
    status: string;
    startedAt: string;
    completedAt?: string;
    duration?: number;
    inputData?: Record<string, any>;
    outputData?: Record<string, any>;
    error?: string;
    tokensUsed?: number;
    costCents?: number;
  }>;
  totalTokens: number;
  totalCost: number;
  errors?: string[];
  warnings?: string[];
}

interface WorkflowTestInterfaceProps {
  workflow: {
    id: string;
    name: string;
    definition: {
      nodes: any[];
      edges: any[];
    };
  };
  onExecuteTest: (scenario: TestScenario) => Promise<TestExecution>;
  onSaveScenario?: (scenario: Omit<TestScenario, 'id' | 'createdAt'>) => Promise<TestScenario>;
  onLoadScenarios?: () => Promise<TestScenario[]>;
  className?: string;
}

export function WorkflowTestInterface({
  workflow,
  onExecuteTest,
  onSaveScenario,
  onLoadScenarios,
  className
}: WorkflowTestInterfaceProps) {
  const [activeTab, setActiveTab] = useState<'run' | 'scenarios' | 'results'>('run');
  const [testScenarios, setTestScenarios] = useState<TestScenario[]>([]);
  const [executions, setExecutions] = useState<TestExecution[]>([]);
  const [currentExecution, setCurrentExecution] = useState<TestExecution | null>(null);
  
  // Current test form
  const [testInput, setTestInput] = useState('{}');
  const [testName, setTestName] = useState('');
  const [testDescription, setTestDescription] = useState('');
  const [isRunning, setIsRunning] = useState(false);
  
  // Scenario management
  const [editingScenario, setEditingScenario] = useState<TestScenario | null>(null);
  const [showScenarioForm, setShowScenarioForm] = useState(false);
  
  // Load scenarios on mount
  useEffect(() => {
    if (onLoadScenarios) {
      onLoadScenarios().then(setTestScenarios).catch(console.error);
    }
  }, [onLoadScenarios]);

  const runTest = async (inputData?: Record<string, any>, scenarioId?: string) => {
    setIsRunning(true);
    try {
      let scenario: TestScenario;
      
      if (scenarioId) {
        const existingScenario = testScenarios.find(s => s.id === scenarioId);
        if (!existingScenario) throw new Error('Scenario not found');
        scenario = existingScenario;
      } else {
        // Create ad-hoc scenario
        scenario = {
          id: `test-${Date.now()}`,
          name: testName || 'Ad-hoc Test',
          description: testDescription,
          inputData: inputData || JSON.parse(testInput || '{}'),
          createdAt: new Date().toISOString()
        };
      }
      
      const execution = await onExecuteTest(scenario);
      setCurrentExecution(execution);
      setExecutions(prev => [execution, ...prev]);
      setActiveTab('results');
    } catch (error) {
      console.error('Test execution failed:', error);
    } finally {
      setIsRunning(false);
    }
  };

  const saveCurrentAsScenario = async () => {
    if (!onSaveScenario) return;
    
    try {
      const scenario = await onSaveScenario({
        name: testName || 'New Test Scenario',
        description: testDescription,
        inputData: JSON.parse(testInput || '{}'),
        tags: ['manual']
      });
      
      setTestScenarios(prev => [scenario, ...prev]);
      setTestName('');
      setTestDescription('');
      setTestInput('{}');
    } catch (error) {
      console.error('Failed to save scenario:', error);
    }
  };

  const loadScenario = (scenario: TestScenario) => {
    setTestInput(JSON.stringify(scenario.inputData, null, 2));
    setTestName(scenario.name);
    setTestDescription(scenario.description || '');
    setActiveTab('run');
  };

  const generateDefaultInput = () => {
    // Generate input based on workflow trigger nodes
    const triggerNodes = workflow.definition.nodes.filter(node => node.type === 'trigger');
    const defaultInput: Record<string, any> = {};
    
    triggerNodes.forEach(node => {
      if (node.data?.trigger_type === 'manual') {
        defaultInput.message = 'Test message for workflow execution';
      } else if (node.data?.trigger_type === 'webhook') {
        defaultInput.webhook_data = { test: true };
      } else if (node.data?.trigger_type === 'schedule') {
        defaultInput.scheduled_time = new Date().toISOString();
      }
    });
    
    return JSON.stringify(defaultInput, null, 2);
  };

  const formatDuration = (ms?: number) => {
    if (!ms) return '—';
    if (ms < 1000) return `${ms}ms`;
    if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
    return `${(ms / 60000).toFixed(1)}m`;
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'running': return <Activity className="w-4 h-4 animate-pulse text-blue-500" />;
      case 'completed': return <CheckCircle className="w-4 h-4 text-green-500" />;
      case 'failed': return <AlertTriangle className="w-4 h-4 text-red-500" />;
      case 'cancelled': return <Square className="w-4 h-4 text-gray-500" />;
      default: return <Clock className="w-4 h-4 text-gray-500" />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'running': return 'text-blue-600 bg-blue-50 border-blue-200';
      case 'completed': return 'text-green-600 bg-green-50 border-green-200';
      case 'failed': return 'text-red-600 bg-red-50 border-red-200';
      case 'cancelled': return 'text-gray-600 bg-gray-50 border-gray-200';
      default: return 'text-gray-600 bg-gray-50 border-gray-200';
    }
  };

  return (
    <TooltipProvider>
      <div className={cn("workflow-test-interface h-full flex flex-col", className)}>
        {/* Header */}
        <div className="p-4 border-b bg-white">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold text-gray-900">Workflow Testing</h2>
              <p className="text-sm text-gray-600">Test {workflow.name} with different scenarios</p>
            </div>
            <div className="flex items-center gap-2">
              <Badge variant="secondary" className="text-xs">
                {workflow.definition.nodes.length} nodes
              </Badge>
              <Badge variant="secondary" className="text-xs">
                {workflow.definition.edges.length} connections
              </Badge>
            </div>
          </div>
        </div>

        {/* Tabs */}
        <Tabs value={activeTab} onValueChange={(value) => setActiveTab(value as any)} className="flex-1 flex flex-col">
          <div className="border-b bg-white px-4">
            <TabsList className="grid w-full max-w-md grid-cols-3">
              <TabsTrigger value="run" className="flex items-center gap-1">
                <Play className="w-4 h-4" />
                Run Test
              </TabsTrigger>
              <TabsTrigger value="scenarios" className="flex items-center gap-1">
                <FileText className="w-4 h-4" />
                Scenarios
              </TabsTrigger>
              <TabsTrigger value="results" className="flex items-center gap-1">
                <Activity className="w-4 h-4" />
                Results
              </TabsTrigger>
            </TabsList>
          </div>

          {/* Run Test Tab */}
          <TabsContent value="run" className="flex-1 p-4 space-y-4">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Test Configuration */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Settings className="w-5 h-5" />
                    Test Configuration
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div>
                    <Label htmlFor="test-name">Test Name (optional)</Label>
                    <Input
                      id="test-name"
                      value={testName}
                      onChange={(e) => setTestName((e as React.ChangeEvent<HTMLSelectElement>).target.value)}
                      placeholder="e.g., Happy Path Test"
                      className="mt-1"
                    />
                  </div>
                  
                  <div>
                    <Label htmlFor="test-description">Description (optional)</Label>
                    <Textarea
                      id="test-description"
                      value={testDescription}
                      onChange={(e) => setTestDescription((e as React.ChangeEvent<HTMLSelectElement>).target.value)}
                      placeholder="Describe what this test validates..."
                      className="mt-1"
                      rows={2}
                    />
                  </div>
                  
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <Label htmlFor="test-input">Input Data (JSON)</Label>
                      <Button
                        size="sm"
                        variant="secondary"
                        onClick={() => setTestInput(generateDefaultInput())}
                      >
                        Generate Default
                      </Button>
                    </div>
                    <Textarea
                      id="test-input"
                      value={testInput}
                      onChange={(e) => setTestInput((e as React.ChangeEvent<HTMLSelectElement>).target.value)}
                      placeholder="Enter JSON input data..."
                      className="mt-1 font-mono text-sm"
                      rows={8}
                    />
                    <p className="text-xs text-gray-500 mt-1">
                      Provide input data that matches your workflow's trigger requirements
                    </p>
                  </div>
                  
                  <div className="flex gap-2">
                    <Button
                      onClick={() => runTest()}
                      disabled={isRunning}
                      className="flex-1"
                    >
                      {isRunning ? (
                        <Activity className="w-4 h-4 mr-2 animate-spin" />
                      ) : (
                        <Play className="w-4 h-4 mr-2" />
                      )}
                      {isRunning ? 'Running...' : 'Run Test'}
                    </Button>
                    
                    {onSaveScenario && (
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Button
                            variant="secondary"
                            onClick={saveCurrentAsScenario}
                            disabled={!testInput.trim()}
                          >
                            <Plus className="w-4 h-4" />
                          </Button>
                        </TooltipTrigger>
                        <TooltipContent>Save as Scenario</TooltipContent>
                      </Tooltip>
                    )}
                  </div>
                </CardContent>
              </Card>

              {/* Quick Actions */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Zap className="w-5 h-5" />
                    Quick Actions
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  {/* Recent Scenarios */}
                  {testScenarios.length > 0 && (
                    <div>
                      <Label className="text-sm font-medium">Recent Scenarios</Label>
                      <div className="mt-2 space-y-2">
                        {testScenarios.slice(0, 3).map(scenario => (
                          <div key={scenario.id} className="flex items-center justify-between p-2 border border-gray-200 rounded">
                            <div className="flex-1 min-w-0">
                              <p className="text-sm font-medium truncate">{scenario.name}</p>
                              <p className="text-xs text-gray-500 truncate">{scenario.description}</p>
                            </div>
                            <div className="flex items-center gap-1">
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() => loadScenario(scenario)}
                              >
                                <Edit className="w-3 h-3" />
                              </Button>
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() => runTest(undefined, scenario.id)}
                                disabled={isRunning}
                              >
                                <Play className="w-3 h-3" />
                              </Button>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                  
                  {/* Sample Tests */}
                  <div>
                    <Label className="text-sm font-medium">Sample Tests</Label>
                    <div className="mt-2 space-y-2">
                      <Button
                        variant="secondary"
                        size="sm"
                        className="w-full justify-start"
                        onClick={() => {
                          setTestInput('{"message": "Hello, can you help me?"}');
                          setTestName('Basic Greeting Test');
                        }}
                      >
                        <Bot className="w-4 h-4 mr-2" />
                        Basic Greeting
                      </Button>
                      <Button
                        variant="secondary"
                        size="sm"
                        className="w-full justify-start"
                        onClick={() => {
                          setTestInput('{"message": "Process this data: [1,2,3,4,5]", "data": [1,2,3,4,5]}');
                          setTestName('Data Processing Test');
                        }}
                      >
                        <Database className="w-4 h-4 mr-2" />
                        Data Processing
                      </Button>
                      <Button
                        variant="secondary"
                        size="sm"
                        className="w-full justify-start"
                        onClick={() => {
                          setTestInput('{"message": "This should trigger an error"}');
                          setTestName('Error Handling Test');
                        }}
                      >
                        <AlertTriangle className="w-4 h-4 mr-2" />
                        Error Handling
                      </Button>
                    </div>
                  </div>
                  
                  {/* Current Execution Status */}
                  {currentExecution && (
                    <div className="p-3 bg-gray-50 rounded-lg">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-medium">Latest Execution</span>
                        <div className={cn("flex items-center gap-1", getStatusColor(currentExecution.status))}>
                          {getStatusIcon(currentExecution.status)}
                          <span className="text-xs capitalize">{currentExecution.status}</span>
                        </div>
                      </div>
                      <div className="grid grid-cols-3 gap-2 text-xs text-gray-600">
                        <div>
                          <span className="block text-gray-500">Duration</span>
                          <span className="font-medium">{formatDuration(currentExecution.duration)}</span>
                        </div>
                        <div>
                          <span className="block text-gray-500">Tokens</span>
                          <span className="font-medium">{currentExecution.totalTokens}</span>
                        </div>
                        <div>
                          <span className="block text-gray-500">Cost</span>
                          <span className="font-medium">${(currentExecution.totalCost / 100).toFixed(4)}</span>
                        </div>
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          {/* Scenarios Tab */}
          <TabsContent value="scenarios" className="flex-1 p-4">
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-medium">Test Scenarios</h3>
                <Button onClick={() => setShowScenarioForm(true)}>
                  <Plus className="w-4 h-4 mr-2" />
                  New Scenario
                </Button>
              </div>
              
              {testScenarios.length === 0 ? (
                <Card>
                  <CardContent className="text-center py-8">
                    <FileText className="w-12 h-12 text-gray-300 mx-auto mb-4" />
                    <h3 className="text-lg font-medium text-gray-900 mb-2">No scenarios yet</h3>
                    <p className="text-gray-600 mb-4">
                      Create test scenarios to systematically validate your workflow
                    </p>
                    <Button onClick={() => setShowScenarioForm(true)}>
                      Create Your First Scenario
                    </Button>
                  </CardContent>
                </Card>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {testScenarios.map(scenario => (
                    <Card key={scenario.id} className="hover:shadow-md transition-shadow">
                      <CardHeader className="pb-3">
                        <div className="flex items-start justify-between">
                          <div className="flex-1 min-w-0">
                            <h4 className="font-medium truncate">{scenario.name}</h4>
                            {scenario.description && (
                              <p className="text-sm text-gray-600 line-clamp-2 mt-1">
                                {scenario.description}
                              </p>
                            )}
                          </div>
                          <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                              <Button variant="ghost" size="sm">
                                <Settings className="w-4 h-4" />
                              </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                              <DropdownMenuItem onClick={() => runTest(undefined, scenario.id)}>
                                <Play className="w-4 h-4 mr-2" />
                                Run Test
                              </DropdownMenuItem>
                              <DropdownMenuItem onClick={() => loadScenario(scenario)}>
                                <Edit className="w-4 h-4 mr-2" />
                                Edit
                              </DropdownMenuItem>
                              <DropdownMenuItem onClick={() => navigator.clipboard.writeText(JSON.stringify(scenario.inputData, null, 2))}>
                                <Copy className="w-4 h-4 mr-2" />
                                Copy Input
                              </DropdownMenuItem>
                              <DropdownMenuSeparator />
                              <DropdownMenuItem className="text-red-600">
                                <Trash2 className="w-4 h-4 mr-2" />
                                Delete
                              </DropdownMenuItem>
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </div>
                      </CardHeader>
                      <CardContent className="pt-0">
                        {scenario.tags && (
                          <div className="flex flex-wrap gap-1 mb-3">
                            {scenario.tags.map(tag => (
                              <Badge key={tag} variant="secondary" className="text-xs">
                                {tag}
                              </Badge>
                            ))}
                          </div>
                        )}
                        <div className="flex gap-2">
                          <Button
                            size="sm"
                            variant="secondary"
                            onClick={() => loadScenario(scenario)}
                            className="flex-1"
                          >
                            Load
                          </Button>
                          <Button
                            size="sm"
                            onClick={() => runTest(undefined, scenario.id)}
                            disabled={isRunning}
                            className="flex-1"
                          >
                            <Play className="w-3 h-3 mr-1" />
                            Run
                          </Button>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              )}
            </div>
          </TabsContent>

          {/* Results Tab */}
          <TabsContent value="results" className="flex-1 p-4">
            <div className="space-y-4">
              <h3 className="text-lg font-medium">Test Results</h3>
              
              {executions.length === 0 ? (
                <Card>
                  <CardContent className="text-center py-8">
                    <Activity className="w-12 h-12 text-gray-300 mx-auto mb-4" />
                    <h3 className="text-lg font-medium text-gray-900 mb-2">No test results yet</h3>
                    <p className="text-gray-600 mb-4">
                      Run some tests to see detailed execution results and performance metrics
                    </p>
                    <Button onClick={() => setActiveTab('run')}>
                      Run Your First Test
                    </Button>
                  </CardContent>
                </Card>
              ) : (
                <div className="space-y-4">
                  {executions.map(execution => (
                    <Card key={execution.id} className={cn("border-l-4", 
                      execution.status === 'completed' && "border-l-green-500",
                      execution.status === 'failed' && "border-l-red-500",
                      execution.status === 'running' && "border-l-blue-500"
                    )}>
                      <CardHeader className="pb-3">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-3">
                            {getStatusIcon(execution.status)}
                            <div>
                              <h4 className="font-medium">
                                {testScenarios.find(s => s.id === execution.scenarioId)?.name || 'Ad-hoc Test'}
                              </h4>
                              <p className="text-sm text-gray-500">
                                Started {formatDateTime(execution.startedAt)}
                              </p>
                            </div>
                          </div>
                          <Badge className={getStatusColor(execution.status)}>
                            {execution.status}
                          </Badge>
                        </div>
                      </CardHeader>
                      <CardContent className="space-y-4">
                        {/* Metrics */}
                        <div className="grid grid-cols-4 gap-4 text-sm">
                          <div className="text-center">
                            <div className="text-gray-500">Duration</div>
                            <div className="font-medium">{formatDuration(execution.duration)}</div>
                          </div>
                          <div className="text-center">
                            <div className="text-gray-500">Nodes</div>
                            <div className="font-medium">{execution.nodeExecutions.length}</div>
                          </div>
                          <div className="text-center">
                            <div className="text-gray-500">Tokens</div>
                            <div className="font-medium">{execution.totalTokens}</div>
                          </div>
                          <div className="text-center">
                            <div className="text-gray-500">Cost</div>
                            <div className="font-medium">${(execution.totalCost / 100).toFixed(4)}</div>
                          </div>
                        </div>
                        
                        {/* Node Executions */}
                        {execution.nodeExecutions.length > 0 && (
                          <div>
                            <h5 className="font-medium mb-2">Node Executions</h5>
                            <div className="space-y-2">
                              {execution.nodeExecutions.map(nodeExec => (
                                <div key={nodeExec.nodeId} className="flex items-center justify-between p-2 bg-gray-50 rounded">
                                  <div className="flex items-center gap-2">
                                    {getStatusIcon(nodeExec.status)}
                                    <span className="text-sm font-medium">{nodeExec.nodeId}</span>
                                    <Badge variant="secondary" className="text-xs">
                                      {nodeExec.nodeType}
                                    </Badge>
                                  </div>
                                  <div className="text-sm text-gray-500">
                                    {formatDuration(nodeExec.duration)}
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                        
                        {/* Errors */}
                        {execution.errors && execution.errors.length > 0 && (
                          <div className="p-3 bg-red-50 border border-red-200 rounded">
                            <h5 className="font-medium text-red-800 mb-2">Errors</h5>
                            <ul className="text-sm text-red-700 space-y-1">
                              {execution.errors.map((error, idx) => (
                                <li key={idx}>• {error}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                        
                        {/* Actions */}
                        <div className="flex gap-2 pt-2 border-t">
                          <Button size="sm" variant="secondary">
                            <Eye className="w-3 h-3 mr-1" />
                            View Details
                          </Button>
                          <Button size="sm" variant="secondary">
                            <Download className="w-3 h-3 mr-1" />
                            Export
                          </Button>
                          <Button size="sm" variant="secondary">
                            <RotateCcw className="w-3 h-3 mr-1" />
                            Rerun
                          </Button>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              )}
            </div>
          </TabsContent>
        </Tabs>
      </div>
    </TooltipProvider>
  );
}