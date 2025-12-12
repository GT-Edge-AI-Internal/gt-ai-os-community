'use client';

import { TestLayout } from '@/components/layout/test-layout';
import { useState, useEffect } from 'react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Plus, Play, Settings, Brain, Code, Shield } from 'lucide-react';
import { mockApi } from '@/lib/mock-api';
import { formatDateOnly } from '@/lib/utils';

export default function TestAgentsPage() {
  const [agents, setAgents] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadAgents();
  }, []);

  const loadAgents = async () => {
    try {
      const data = await mockApi.agents.list();
      setAgents(data.agents);
    } catch (error) {
      console.error('Failed to load agents:', error);
    } finally {
      setLoading(false);
    }
  };

  const getAgentIcon = (type: string) => {
    switch (type) {
      case 'research': return <Brain className="w-5 h-5" />;
      case 'coding': return <Code className="w-5 h-5" />;
      case 'security': return <Shield className="w-5 h-5" />;
      default: return <Brain className="w-5 h-5" />;
    }
  };

  return (
    <TestLayout>
      <div className="p-6">
        <div className="mb-6 flex justify-between items-center">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">AI Agents</h1>
            <p className="text-gray-600 mt-1">Manage your autonomous AI agents</p>
          </div>
          <Button className="bg-green-600 hover:bg-green-700 text-white">
            <Plus className="w-4 h-4 mr-2" />
            Create Agent
          </Button>
        </div>

        {loading ? (
          <div className="flex justify-center items-center h-64">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-green-600"></div>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {agents.map((agent) => (
              <Card key={agent.id} className="p-6 hover:shadow-lg transition-shadow">
                <div className="flex items-start justify-between mb-4">
                  <div className="flex items-center">
                    <div className="p-2 bg-green-100 rounded-lg mr-3">
                      {getAgentIcon(agent.agent_type)}
                    </div>
                    <div>
                      <h3 className="font-semibold text-gray-900">{agent.name}</h3>
                      <Badge variant="secondary" className="mt-1">
                        {agent.agent_type}
                      </Badge>
                    </div>
                  </div>
                  <Badge 
                    className={`${
                      agent.status === 'idle' ? 'bg-gray-100 text-gray-700' : 'bg-green-100 text-green-700'
                    }`}
                  >
                    {agent.status}
                  </Badge>
                </div>
                
                <p className="text-sm text-gray-600 mb-4">{agent.description}</p>
                
                <div className="flex flex-wrap gap-2 mb-4">
                  {agent.capabilities.slice(0, 3).map((cap: string, idx: number) => (
                    <Badge key={idx} variant="secondary" className="text-xs">
                      {cap.replace('_', ' ')}
                    </Badge>
                  ))}
                </div>
                
                <div className="flex items-center justify-between text-sm text-gray-500 mb-4">
                  <span>Executions: {agent.execution_count}</span>
                  <span>Last run: {formatDateOnly(agent.last_execution)}</span>
                </div>
                
                <div className="flex gap-2">
                  <Button className="flex-1" variant="secondary">
                    <Settings className="w-4 h-4 mr-2" />
                    Configure
                  </Button>
                  <Button className="flex-1 bg-green-600 hover:bg-green-700 text-white">
                    <Play className="w-4 h-4 mr-2" />
                    Execute
                  </Button>
                </div>
              </Card>
            ))}
          </div>
        )}
      </div>
    </TestLayout>
  );
}