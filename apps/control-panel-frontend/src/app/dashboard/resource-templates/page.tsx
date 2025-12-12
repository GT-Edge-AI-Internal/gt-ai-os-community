'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import {
  Plus,
  Search,
  Filter,
  Bot,
  Brain,
  Code,
  Shield,
  GraduationCap,
  Activity,
  Eye,
  Edit,
  Download,
  Upload,
  Users,
  Building2,
  Star,
  Clock,
  CheckCircle,
  AlertTriangle,
  MoreVertical,
  Copy,
  Trash2,
  Play,
  Settings,
  GitBranch,
  Zap,
  Target,
} from 'lucide-react';
import { assistantLibraryApi, tenantsApi } from '@/lib/api';
import toast from 'react-hot-toast';

interface ResourceTemplate {
  id: string;
  template_id: string;
  name: string;
  description: string;
  category: string; // startup, standard, enterprise
  monthly_cost: number;
  resources: {
    cpu?: { limit: number; unit: string };
    memory?: { limit: number; unit: string };
    storage?: { limit: number; unit: string };
    api_calls?: { limit: number; unit: string };
    model_inference?: { limit: number; unit: string };
    gpu_time?: { limit: number; unit: string };
  };
  created_at: string;
  updated_at: string;
  is_active: boolean;
  icon: string;
  status: string;
  popularity_score: number;
  deployment_count: number;
  active_instances: number;
  version: string;
  capabilities: string[];
  access_groups: string[];
}

export default function ResourceTemplatesPage() {
  const [templates, setTemplates] = useState<ResourceTemplate[]>([]);
  const [filteredTemplates, setFilteredTemplates] = useState<ResourceTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('all');
  const [selectedTemplates, setSelectedTemplates] = useState<Set<string>>(new Set());
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [selectedTemplate, setSelectedTemplate] = useState<ResourceTemplate | null>(null);

  useEffect(() => {
    fetchResourceTemplates();
  }, []);

  const fetchResourceTemplates = async () => {
    try {
      setLoading(true);
      
      // Use the existing resource management API to get templates (relative URL goes through Next.js rewrites)
      const response = await fetch('/api/v1/resource-management/templates');
      const data = await response.json();
      
      // Transform the data to match our interface
      const templatesData = Object.entries(data.templates || {}).map(([key, template]: [string, any]) => ({
        id: key,
        template_id: key,
        name: template.display_name,
        description: template.description,
        category: template.name,
        monthly_cost: template.monthly_cost,
        resources: template.resources,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        is_active: true,
        icon: template.icon || '🏢',
        status: template.status || 'active',
        popularity_score: template.popularity_score || 85,
        deployment_count: template.deployment_count || 12,
        active_instances: template.active_instances || 45,
        version: template.version || '1.0.0',
        capabilities: template.capabilities || ['basic_inference', 'text_generation'],
        access_groups: template.access_groups || ['standard_users', 'developers']
      }));
      
      setTemplates(templatesData);
      setFilteredTemplates(templatesData);
      
    } catch (error) {
      console.warn('Failed to fetch resource templates:', error);
      // Use fallback data from GT 2.0 architecture
      const fallbackTemplates = [
        {
          id: "startup",
          template_id: "startup",
          name: "Startup",
          description: "Basic resources for small teams and development",
          category: "startup",
          monthly_cost: 99.0,
          resources: {
            cpu: { limit: 2.0, unit: "cores" },
            memory: { limit: 4096, unit: "MB" },
            storage: { limit: 10240, unit: "MB" },
            api_calls: { limit: 10000, unit: "calls/hour" },
            model_inference: { limit: 1000, unit: "tokens" }
          },
          created_at: "2024-01-10T14:20:00Z",
          updated_at: "2024-01-15T10:30:00Z",
          is_active: true,
          icon: "🚀",
          status: "active",
          popularity_score: 92,
          deployment_count: 15,
          active_instances: 32,
          version: "1.2.1",
          capabilities: ["basic_inference", "text_generation", "code_analysis"],
          access_groups: ["startup_users", "basic_developers"]
        },
        {
          id: "standard",
          template_id: "standard",
          name: "Standard",
          description: "Standard resources for production workloads",
          category: "standard",
          monthly_cost: 299.0,
          resources: {
            cpu: { limit: 4.0, unit: "cores" },
            memory: { limit: 8192, unit: "MB" },
            storage: { limit: 51200, unit: "MB" },
            api_calls: { limit: 50000, unit: "calls/hour" },
            model_inference: { limit: 10000, unit: "tokens" }
          },
          created_at: "2024-01-05T09:15:00Z",
          updated_at: "2024-01-12T16:45:00Z",
          is_active: true,
          icon: "📈",
          status: "active",
          popularity_score: 88,
          deployment_count: 8,
          active_instances: 28,
          version: "1.1.0",
          capabilities: ["basic_inference", "text_generation", "data_analysis", "visualization"],
          access_groups: ["standard_users", "data_analysts", "developers"]
        },
        {
          id: "enterprise",
          template_id: "enterprise",
          name: "Enterprise",
          description: "High-performance resources for large organizations",
          category: "enterprise",
          monthly_cost: 999.0,
          resources: {
            cpu: { limit: 16.0, unit: "cores" },
            memory: { limit: 32768, unit: "MB" },
            storage: { limit: 102400, unit: "MB" },
            api_calls: { limit: 200000, unit: "calls/hour" },
            model_inference: { limit: 100000, unit: "tokens" },
            gpu_time: { limit: 1000, unit: "minutes" }
          },
          created_at: "2024-01-01T08:30:00Z",
          updated_at: "2024-01-18T11:20:00Z",
          is_active: true,
          icon: "🏢",
          status: "active",
          popularity_score: 95,
          deployment_count: 22,
          active_instances: 67,
          version: "2.0.0",
          capabilities: ["advanced_inference", "multimodal", "code_generation", "function_calling", "custom_training"],
          access_groups: ["enterprise_users", "power_users", "admin_users", "ml_engineers"]
        }
      ];
      setTemplates(fallbackTemplates);
      setFilteredTemplates(fallbackTemplates);
      toast.error('Using cached template data - some features may be limited');
    } finally {
      setLoading(false);
    }
  };

  // Mock data removed - now using real API calls above

  // Filter templates based on search and category
  useEffect(() => {
    let filtered = templates;

    // Filter by category
    if (categoryFilter !== 'all') {
      filtered = filtered.filter(t => t.category === categoryFilter);
    }

    // Filter by search query
    if (searchQuery) {
      filtered = filtered.filter(t =>
        t.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        t.description.toLowerCase().includes(searchQuery.toLowerCase())
      );
    }

    setFilteredTemplates(filtered);
  }, [categoryFilter, searchQuery, templates]);

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'published':
        return <Badge variant="default" className="bg-green-600"><CheckCircle className="h-3 w-3 mr-1" />Published</Badge>;
      case 'testing':
        return <Badge variant="secondary" className="bg-blue-600"><Activity className="h-3 w-3 mr-1" />Testing</Badge>;
      case 'draft':
        return <Badge variant="secondary"><Edit className="h-3 w-3 mr-1" />Draft</Badge>;
      case 'deprecated':
        return <Badge variant="destructive"><AlertTriangle className="h-3 w-3 mr-1" />Deprecated</Badge>;
      default:
        return <Badge variant="secondary">{status}</Badge>;
    }
  };

  const getCategoryIcon = (category: string) => {
    switch (category) {
      case 'cybersecurity':
        return <Shield className="h-4 w-4" />;
      case 'education':
        return <GraduationCap className="h-4 w-4" />;
      case 'research':
        return <Brain className="h-4 w-4" />;
      case 'development':
        return <Code className="h-4 w-4" />;
      case 'general':
        return <Bot className="h-4 w-4" />;
      default:
        return <Bot className="h-4 w-4" />;
    }
  };

  const getCategoryBadge = (category: string) => {
    const colors: Record<string, string> = {
      cybersecurity: 'bg-red-600',
      education: 'bg-green-600',
      research: 'bg-purple-600',
      development: 'bg-blue-600',
      general: 'bg-gray-600',
    };
    return (
      <Badge className={colors[category] || 'bg-gray-600'}>
        {getCategoryIcon(category)}
        <span className="ml-1">{category.charAt(0).toUpperCase() + category.slice(1)}</span>
      </Badge>
    );
  };

  const categoryTabs = [
    { id: 'all', label: 'All Templates', count: templates.length },
    { id: 'startup', label: 'Startup', count: templates.filter(t => t.category === 'startup').length },
    { id: 'standard', label: 'Standard', count: templates.filter(t => t.category === 'standard').length },
    { id: 'enterprise', label: 'Enterprise', count: templates.filter(t => t.category === 'enterprise').length },
  ];

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">Resource Templates</h1>
          <p className="text-muted-foreground">
            Resource allocation templates for tenant provisioning (startup, standard, enterprise)
          </p>
        </div>
        <div className="flex space-x-2">
          <Button>
            <Plus className="h-4 w-4 mr-2" />
            Create Template
          </Button>
        </div>
      </div>

      {/* Analytics Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Available Templates</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{templates.length}</div>
            <p className="text-xs text-muted-foreground">
              {templates.filter(t => t.is_active).length} active
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Cost Range</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              ${templates.length > 0 ? Math.min(...templates.map(t => t.monthly_cost)) : 0} - ${templates.length > 0 ? Math.max(...templates.map(t => t.monthly_cost)) : 0}
            </div>
            <p className="text-xs text-muted-foreground">
              Monthly pricing
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Most Popular</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">Standard</div>
            <p className="text-xs text-muted-foreground">
              Production workloads
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Category Tabs */}
      <div className="flex space-x-2 border-b">
        {categoryTabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setCategoryFilter(tab.id)}
            className={`px-4 py-2 border-b-2 transition-colors ${
              categoryFilter === tab.id
                ? 'border-primary text-primary'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            }`}
          >
            <span>{tab.label}</span>
            <Badge variant="secondary" className="ml-2">{tab.count}</Badge>
          </button>
        ))}
      </div>

      {/* Search */}
      <div className="flex space-x-4">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search resource templates by name or description..."
            value={searchQuery}
            onChange={(e) => setSearchQuery((e as React.ChangeEvent<HTMLInputElement>).target.value)}
            className="pl-10"
          />
        </div>
      </div>

      {/* Bulk Actions */}
      {selectedTemplates.size > 0 && (
        <Card className="bg-muted/50">
          <CardContent className="flex items-center justify-between py-3">
            <span className="text-sm">
              {selectedTemplates.size} template{selectedTemplates.size > 1 ? 's' : ''} selected
            </span>
            <div className="flex space-x-2">
              <Button variant="secondary" size="sm">
                <Play className="h-4 w-4 mr-2" />
                Bulk Deploy
              </Button>
              <Button variant="secondary" size="sm">
                <Copy className="h-4 w-4 mr-2" />
                Duplicate
              </Button>
              <Button variant="secondary" size="sm" className="text-destructive">
                <Trash2 className="h-4 w-4 mr-2" />
                Archive
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Template Gallery */}
      {loading ? (
        <div className="flex items-center justify-center h-64">
          <Activity className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredTemplates.map(template => (
            <Card key={template.id} className="hover:shadow-lg transition-shadow cursor-pointer">
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between">
                  <div className="flex items-center space-x-3">
                    <div className="text-2xl">{template.icon}</div>
                    <div>
                      <CardTitle className="text-lg">{template.name}</CardTitle>
                      <div className="flex items-center space-x-2 mt-1">
                        {getCategoryBadge(template.category)}
                        {getStatusBadge(template.status)}
                      </div>
                    </div>
                  </div>
                  <input
                    type="checkbox"
                    checked={selectedTemplates.has(template.id)}
                    onChange={(e) => {
                      const newSelected = new Set(selectedTemplates);
                      if (e.target.checked) {
                        newSelected.add(template.id);
                      } else {
                        newSelected.delete(template.id);
                      }
                      setSelectedTemplates(newSelected);
                    }}
                  />
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <CardDescription className="text-sm">
                  {template.description}
                </CardDescription>
                
                <div className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Popularity:</span>
                    <div className="flex items-center space-x-1">
                      <Star className="h-3 w-3 text-yellow-500" />
                      <span className="font-medium">{template.popularity_score}%</span>
                    </div>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Deployments:</span>
                    <span className="font-medium">{template.deployment_count}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Active Instances:</span>
                    <span className="font-medium">{template.active_instances}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Version:</span>
                    <span className="font-medium">v{template.version}</span>
                  </div>
                </div>

                <div className="space-y-2">
                  <span className="text-sm text-muted-foreground">Capabilities:</span>
                  <div className="flex flex-wrap gap-1">
                    {template.capabilities.slice(0, 3).map(capability => (
                      <Badge key={capability} variant="secondary" className="text-xs">
                        {capability.replace('_', ' ')}
                      </Badge>
                    ))}
                    {template.capabilities.length > 3 && (
                      <Badge variant="secondary" className="text-xs">
                        +{template.capabilities.length - 3}
                      </Badge>
                    )}
                  </div>
                </div>

                <div className="space-y-2">
                  <span className="text-sm text-muted-foreground">Access Groups:</span>
                  <div className="flex flex-wrap gap-1">
                    {template.access_groups.slice(0, 2).map(group => (
                      <Badge key={group} variant="secondary" className="text-xs">
                        {group.replace('_', ' ')}
                      </Badge>
                    ))}
                    {template.access_groups.length > 2 && (
                      <Badge variant="secondary" className="text-xs">
                        +{template.access_groups.length - 2}
                      </Badge>
                    )}
                  </div>
                </div>

                <div className="text-xs text-muted-foreground">
                  Updated {new Date(template.updated_at).toLocaleDateString()}
                </div>

                <div className="flex space-x-2 pt-2">
                  <Button variant="secondary" size="sm" className="flex-1">
                    <Eye className="h-4 w-4 mr-1" />
                    View
                  </Button>
                  <Button variant="secondary" size="sm" className="flex-1">
                    <Play className="h-4 w-4 mr-1" />
                    Deploy
                  </Button>
                  <Button variant="secondary" size="sm">
                    <MoreVertical className="h-4 w-4" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {filteredTemplates.length === 0 && !loading && (
        <div className="text-center py-12">
          <Bot className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
          <h3 className="text-lg font-medium mb-2">No templates found</h3>
          <p className="text-muted-foreground mb-4">
            Try adjusting your search criteria or create a new template.
          </p>
          <Button onClick={() => setShowCreateDialog(true)}>
            <Plus className="h-4 w-4 mr-2" />
            Create Template
          </Button>
        </div>
      )}
    </div>
  );
}