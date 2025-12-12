'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Plus,
  Search,
  Filter,
  Brain,
  Database,
  GitBranch,
  Webhook,
  ExternalLink,
  GraduationCap,
  RefreshCw,
  Settings,
  CheckCircle,
  AlertTriangle,
  XCircle,
  Activity,
  Zap,
  Shield,
  Users,
  Building2,
  MoreVertical,
} from 'lucide-react';
import { useAuthStore } from '@/stores/auth-store';
import { useRouter } from 'next/navigation';

interface Resource {
  id: number;
  uuid: string;
  name: string;
  description?: string;
  resource_type: string;
  resource_subtype?: string;
  provider: string;
  model_name?: string;
  personalization_mode: string;
  health_status: string;
  is_active: boolean;
  priority: number;
  max_requests_per_minute: number;
  max_tokens_per_request: number;
  cost_per_1k_tokens: number;
  last_health_check?: string;
  created_at: string;
  updated_at: string;
}

export default function ResourcesPage() {
  const { user } = useAuthStore();
  const router = useRouter();
  const [resources, setResources] = useState<Resource[]>([]);
  const [filteredResources, setFilteredResources] = useState<Resource[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedTab, setSelectedTab] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedResources, setSelectedResources] = useState<Set<number>>(new Set());

  // Mock data for development
  useEffect(() => {
    const mockResources: Resource[] = [
      {
        id: 1,
        uuid: '123e4567-e89b-12d3-a456-426614174000',
        name: 'GPT-4 Turbo',
        description: 'Advanced language model for complex tasks',
        resource_type: 'ai_ml',
        resource_subtype: 'llm',
        provider: 'openai',
        model_name: 'gpt-4-turbo-preview',
        personalization_mode: 'shared',
        health_status: 'healthy',
        is_active: true,
        priority: 100,
        max_requests_per_minute: 500,
        max_tokens_per_request: 8000,
        cost_per_1k_tokens: 0.03,
        last_health_check: new Date().toISOString(),
        created_at: '2024-01-01T00:00:00Z',
        updated_at: new Date().toISOString(),
      },
      {
        id: 2,
        uuid: '223e4567-e89b-12d3-a456-426614174001',
        name: 'Llama 3.1 70B (Groq)',
        description: 'Fast inference via Groq Cloud',
        resource_type: 'ai_ml',
        resource_subtype: 'llm',
        provider: 'groq',
        model_name: 'llama-3.1-70b-versatile',
        personalization_mode: 'shared',
        health_status: 'healthy',
        is_active: true,
        priority: 90,
        max_requests_per_minute: 1000,
        max_tokens_per_request: 4096,
        cost_per_1k_tokens: 0.008,
        last_health_check: new Date().toISOString(),
        created_at: '2024-01-02T00:00:00Z',
        updated_at: new Date().toISOString(),
      },
      {
        id: 3,
        uuid: '323e4567-e89b-12d3-a456-426614174002',
        name: 'BGE-M3 Embeddings',
        description: '1024-dimension embedding model on GPU cluster',
        resource_type: 'ai_ml',
        resource_subtype: 'embedding',
        provider: 'local',
        model_name: 'BAAI/bge-m3',
        personalization_mode: 'shared',
        health_status: 'healthy',
        is_active: true,
        priority: 95,
        max_requests_per_minute: 2000,
        max_tokens_per_request: 512,
        cost_per_1k_tokens: 0.0001,
        last_health_check: new Date().toISOString(),
        created_at: '2024-01-03T00:00:00Z',
        updated_at: new Date().toISOString(),
      },
      {
        id: 4,
        uuid: '423e4567-e89b-12d3-a456-426614174003',
        name: 'ChromaDB Vector Store',
        description: 'Encrypted vector database with user isolation',
        resource_type: 'rag_engine',
        resource_subtype: 'vector_database',
        provider: 'local',
        model_name: 'chromadb',
        personalization_mode: 'user_scoped',
        health_status: 'healthy',
        is_active: true,
        priority: 100,
        max_requests_per_minute: 5000,
        max_tokens_per_request: 0,
        cost_per_1k_tokens: 0,
        last_health_check: new Date().toISOString(),
        created_at: '2024-01-04T00:00:00Z',
        updated_at: new Date().toISOString(),
      },
      {
        id: 5,
        uuid: '523e4567-e89b-12d3-a456-426614174004',
        name: 'Document Processor',
        description: 'Unstructured.io chunking engine',
        resource_type: 'rag_engine',
        resource_subtype: 'document_processor',
        provider: 'local',
        personalization_mode: 'shared',
        health_status: 'healthy',
        is_active: true,
        priority: 100,
        max_requests_per_minute: 100,
        max_tokens_per_request: 0,
        cost_per_1k_tokens: 0,
        last_health_check: new Date().toISOString(),
        created_at: '2024-01-05T00:00:00Z',
        updated_at: new Date().toISOString(),
      },
      {
        id: 6,
        uuid: '623e4567-e89b-12d3-a456-426614174005',
        name: 'Research Agent',
        description: 'Multi-step research workflow orchestrator',
        resource_type: 'agentic_workflow',
        resource_subtype: 'single_agent',
        provider: 'local',
        personalization_mode: 'user_scoped',
        health_status: 'healthy',
        is_active: true,
        priority: 90,
        max_requests_per_minute: 50,
        max_tokens_per_request: 0,
        cost_per_1k_tokens: 0,
        last_health_check: new Date().toISOString(),
        created_at: '2024-01-06T00:00:00Z',
        updated_at: new Date().toISOString(),
      },
      {
        id: 7,
        uuid: '723e4567-e89b-12d3-a456-426614174006',
        name: 'GitHub Connector',
        description: 'GitHub API integration for DevOps workflows',
        resource_type: 'app_integration',
        resource_subtype: 'development',
        provider: 'custom',
        personalization_mode: 'user_scoped',
        health_status: 'unhealthy',
        is_active: true,
        priority: 80,
        max_requests_per_minute: 60,
        max_tokens_per_request: 0,
        cost_per_1k_tokens: 0,
        last_health_check: new Date(Date.now() - 3600000).toISOString(),
        created_at: '2024-01-07T00:00:00Z',
        updated_at: new Date().toISOString(),
      },
      {
        id: 8,
        uuid: '823e4567-e89b-12d3-a456-426614174007',
        name: 'Canvas LMS',
        description: 'Educational platform integration',
        resource_type: 'external_service',
        resource_subtype: 'educational',
        provider: 'canvas',
        personalization_mode: 'user_scoped',
        health_status: 'healthy',
        is_active: true,
        priority: 85,
        max_requests_per_minute: 100,
        max_tokens_per_request: 0,
        cost_per_1k_tokens: 0,
        last_health_check: new Date().toISOString(),
        created_at: '2024-01-08T00:00:00Z',
        updated_at: new Date().toISOString(),
      },
      {
        id: 9,
        uuid: '923e4567-e89b-12d3-a456-426614174008',
        name: 'Strategic Chess Engine',
        description: 'AI-powered chess with learning analytics',
        resource_type: 'ai_literacy',
        resource_subtype: 'strategic_game',
        provider: 'local',
        personalization_mode: 'user_scoped',
        health_status: 'healthy',
        is_active: true,
        priority: 70,
        max_requests_per_minute: 200,
        max_tokens_per_request: 0,
        cost_per_1k_tokens: 0,
        last_health_check: new Date().toISOString(),
        created_at: '2024-01-09T00:00:00Z',
        updated_at: new Date().toISOString(),
      },
    ];

    setResources(mockResources);
    setFilteredResources(mockResources);
    setLoading(false);
  }, []);

  // Filter resources based on tab and search
  useEffect(() => {
    let filtered = resources;

    // Filter by resource type
    if (selectedTab !== 'all') {
      filtered = filtered.filter(r => r.resource_type === selectedTab);
    }

    // Filter by search query
    if (searchQuery) {
      filtered = filtered.filter(r =>
        r.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        r.description?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        r.provider.toLowerCase().includes(searchQuery.toLowerCase())
      );
    }

    setFilteredResources(filtered);
  }, [selectedTab, searchQuery, resources]);

  const getResourceIcon = (type: string) => {
    switch (type) {
      case 'ai_ml': return <Brain className="h-5 w-5" />;
      case 'rag_engine': return <Database className="h-5 w-5" />;
      case 'agentic_workflow': return <GitBranch className="h-5 w-5" />;
      case 'app_integration': return <Webhook className="h-5 w-5" />;
      case 'external_service': return <ExternalLink className="h-5 w-5" />;
      case 'ai_literacy': return <GraduationCap className="h-5 w-5" />;
      default: return <Zap className="h-5 w-5" />;
    }
  };

  const getHealthBadge = (status: string) => {
    switch (status) {
      case 'healthy':
        return <Badge variant="default" className="bg-green-600"><CheckCircle className="h-3 w-3 mr-1" />Healthy</Badge>;
      case 'unhealthy':
        return <Badge variant="destructive"><XCircle className="h-3 w-3 mr-1" />Unhealthy</Badge>;
      default:
        return <Badge variant="secondary"><AlertTriangle className="h-3 w-3 mr-1" />Unknown</Badge>;
    }
  };

  const getPersonalizationBadge = (mode: string) => {
    switch (mode) {
      case 'shared':
        return <Badge variant="secondary"><Users className="h-3 w-3 mr-1" />Shared</Badge>;
      case 'user_scoped':
        return <Badge variant="secondary"><Shield className="h-3 w-3 mr-1" />User-Scoped</Badge>;
      case 'session_based':
        return <Badge variant="secondary"><Activity className="h-3 w-3 mr-1" />Session-Based</Badge>;
      default:
        return <Badge variant="secondary">{mode}</Badge>;
    }
  };

  const resourceTabs = [
    { id: 'all', label: 'All Resources', count: resources.length },
    { id: 'ai_ml', label: 'AI/ML Models', icon: <Brain className="h-4 w-4" />, count: resources.filter(r => r.resource_type === 'ai_ml').length },
    { id: 'rag_engine', label: 'RAG Engines', icon: <Database className="h-4 w-4" />, count: resources.filter(r => r.resource_type === 'rag_engine').length },
    { id: 'agentic_workflow', label: 'Agents', icon: <GitBranch className="h-4 w-4" />, count: resources.filter(r => r.resource_type === 'agentic_workflow').length },
    { id: 'app_integration', label: 'Integrations', icon: <Webhook className="h-4 w-4" />, count: resources.filter(r => r.resource_type === 'app_integration').length },
    { id: 'external_service', label: 'External', icon: <ExternalLink className="h-4 w-4" />, count: resources.filter(r => r.resource_type === 'external_service').length },
    { id: 'ai_literacy', label: 'AI Literacy', icon: <GraduationCap className="h-4 w-4" />, count: resources.filter(r => r.resource_type === 'ai_literacy').length },
  ];

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">Resource Management</h1>
          <p className="text-muted-foreground">
            Manage all GT 2.0 resources across six comprehensive families
          </p>
        </div>
        <div className="flex space-x-2">
          <Button variant="secondary">
            <RefreshCw className="h-4 w-4 mr-2" />
            Health Check All
          </Button>
          <Button>
            <Plus className="h-4 w-4 mr-2" />
            Add Resource
          </Button>
        </div>
      </div>

      {/* Resource Type Tabs */}
      <div className="flex space-x-2 border-b">
        {resourceTabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setSelectedTab(tab.id)}
            className={`flex items-center space-x-2 px-4 py-2 border-b-2 transition-colors ${
              selectedTab === tab.id
                ? 'border-primary text-primary'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            }`}
          >
            {tab.icon}
            <span>{tab.label}</span>
            <Badge variant="secondary" className="ml-2">{tab.count}</Badge>
          </button>
        ))}
      </div>

      {/* Search and Filters */}
      <div className="flex space-x-4">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search resources by name, provider, or description..."
            value={searchQuery}
            onChange={(e) => setSearchQuery((e as React.ChangeEvent<HTMLInputElement>).target.value)}
            className="pl-10"
          />
        </div>
        <Button variant="secondary">
          <Filter className="h-4 w-4 mr-2" />
          Filters
        </Button>
      </div>

      {/* Bulk Actions */}
      {selectedResources.size > 0 && (
        <Card className="bg-muted/50">
          <CardContent className="flex items-center justify-between py-3">
            <span className="text-sm">
              {selectedResources.size} resource{selectedResources.size > 1 ? 's' : ''} selected
            </span>
            <div className="flex space-x-2">
              <Button variant="secondary" size="sm">
                <Building2 className="h-4 w-4 mr-2" />
                Assign to Tenants
              </Button>
              <Button variant="secondary" size="sm">
                <RefreshCw className="h-4 w-4 mr-2" />
                Health Check
              </Button>
              <Button variant="secondary" size="sm" className="text-destructive">
                Disable
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Resources Grid */}
      {loading ? (
        <div className="flex items-center justify-center h-64">
          <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredResources.map(resource => (
            <Card key={resource.id} className="hover:shadow-md transition-shadow">
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between">
                  <div className="flex items-center space-x-2">
                    {getResourceIcon(resource.resource_type)}
                    <div>
                      <CardTitle className="text-lg">{resource.name}</CardTitle>
                      <p className="text-xs text-muted-foreground">{resource.provider}</p>
                    </div>
                  </div>
                  <div className="flex items-center space-x-2">
                    <input
                      type="checkbox"
                      checked={selectedResources.has(resource.id)}
                      onChange={(e) => {
                        const newSelected = new Set(selectedResources);
                        if (e.target.checked) {
                          newSelected.add(resource.id);
                        } else {
                          newSelected.delete(resource.id);
                        }
                        setSelectedResources(newSelected);
                      }}
                      className="h-4 w-4"
                    />
                    <Button variant="ghost" size="sm">
                      <MoreVertical className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                {resource.description && (
                  <p className="text-sm text-muted-foreground">{resource.description}</p>
                )}
                
                <div className="flex flex-wrap gap-2">
                  {getHealthBadge(resource.health_status)}
                  {getPersonalizationBadge(resource.personalization_mode)}
                  {resource.model_name && (
                    <Badge variant="secondary" className="text-xs">{resource.model_name}</Badge>
                  )}
                </div>

                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div>
                    <span className="text-muted-foreground">Rate Limit:</span>
                    <p className="font-medium">{resource.max_requests_per_minute}/min</p>
                  </div>
                  {resource.max_tokens_per_request > 0 && (
                    <div>
                      <span className="text-muted-foreground">Max Tokens:</span>
                      <p className="font-medium">{resource.max_tokens_per_request.toLocaleString()}</p>
                    </div>
                  )}
                  {resource.cost_per_1k_tokens > 0 && (
                    <div>
                      <span className="text-muted-foreground">Cost/1K:</span>
                      <p className="font-medium">${resource.cost_per_1k_tokens}</p>
                    </div>
                  )}
                  <div>
                    <span className="text-muted-foreground">Priority:</span>
                    <p className="font-medium">{resource.priority}</p>
                  </div>
                </div>

                {resource.last_health_check && (
                  <div className="pt-2 border-t">
                    <p className="text-xs text-muted-foreground">
                      Last checked: {new Date(resource.last_health_check).toLocaleTimeString()}
                    </p>
                  </div>
                )}

                <div className="flex space-x-2 pt-2">
                  <Button variant="secondary" size="sm" className="flex-1">
                    <Settings className="h-3 w-3 mr-1" />
                    Configure
                  </Button>
                  <Button variant="secondary" size="sm" className="flex-1">
                    <Building2 className="h-3 w-3 mr-1" />
                    Assign
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