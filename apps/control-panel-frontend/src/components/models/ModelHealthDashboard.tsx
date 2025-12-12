"use client";

import { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { 
  CheckCircle, 
  AlertCircle, 
  Clock, 
  RefreshCw,
  Zap,
  Cpu,
  Activity,
  TrendingUp
} from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar } from 'recharts';

interface HealthMetrics {
  total_models: number;
  healthy_models: number;
  unhealthy_models: number;
  unknown_models: number;
  avg_latency: number;
  uptime_percentage: number;
  last_updated: string;
}

interface ModelHealth {
  model_id: string;
  name: string;
  provider: string;
  health_status: 'healthy' | 'unhealthy' | 'unknown';
  latency_ms: number;
  success_rate: number;
  last_check: string;
  error_message?: string;
  uptime_24h: number;
}

// Mock data for charts
const latencyData = [
  { time: '00:00', groq: 120, bge_m3: 45 },
  { time: '04:00', groq: 135, bge_m3: 52 },
  { time: '08:00', groq: 180, bge_m3: 67 },
  { time: '12:00', groq: 220, bge_m3: 89 },
  { time: '16:00', groq: 195, bge_m3: 71 },
  { time: '20:00', groq: 165, bge_m3: 58 },
];

const requestVolumeData = [
  { hour: '00', requests: 120 },
  { hour: '04', requests: 89 },
  { hour: '08', requests: 456 },
  { hour: '12', requests: 892 },
  { hour: '16', requests: 743 },
  { hour: '20', requests: 567 },
];

export default function ModelHealthDashboard() {
  const [metrics, setMetrics] = useState<HealthMetrics | null>(null);
  const [modelHealth, setModelHealth] = useState<ModelHealth[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    loadHealthData();
  }, []);

  const loadHealthData = async () => {
    setLoading(true);
    
    // Mock data - replace with API calls
    await new Promise(resolve => setTimeout(resolve, 1000));
    
    const mockMetrics: HealthMetrics = {
      total_models: 20,
      healthy_models: 18,
      unhealthy_models: 1,
      unknown_models: 1,
      avg_latency: 167,
      uptime_percentage: 99.2,
      last_updated: new Date().toISOString()
    };
    
    const mockModelHealth: ModelHealth[] = [
      {
        model_id: "llama-3.3-70b-versatile",
        name: "Llama 3.3 70B Versatile",
        provider: "groq",
        health_status: "healthy",
        latency_ms: 234,
        success_rate: 99.8,
        last_check: new Date(Date.now() - 30000).toISOString(),
        uptime_24h: 99.9
      },
      {
        model_id: "bge-m3",
        name: "BGE-M3 Embeddings",
        provider: "external",
        health_status: "healthy",
        latency_ms: 67,
        success_rate: 100.0,
        last_check: new Date(Date.now() - 15000).toISOString(),
        uptime_24h: 99.5
      },
      {
        model_id: "whisper-large-v3",
        name: "Whisper Large v3",
        provider: "groq",
        health_status: "unhealthy",
        latency_ms: 0,
        success_rate: 87.2,
        last_check: new Date(Date.now() - 120000).toISOString(),
        error_message: "API rate limit exceeded",
        uptime_24h: 87.2
      },
      {
        model_id: "llama-3.1-405b-reasoning",
        name: "Llama 3.1 405B Reasoning",
        provider: "groq",
        health_status: "unknown",
        latency_ms: 0,
        success_rate: 0,
        last_check: new Date(Date.now() - 300000).toISOString(),
        uptime_24h: 0
      }
    ];
    
    setMetrics(mockMetrics);
    setModelHealth(mockModelHealth);
    setLoading(false);
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    await loadHealthData();
    setRefreshing(false);
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'healthy':
        return <CheckCircle className="w-4 h-4 text-green-600" />;
      case 'unhealthy':
        return <AlertCircle className="w-4 h-4 text-red-600" />;
      default:
        return <Clock className="w-4 h-4 text-yellow-600" />;
    }
  };

  const getStatusBadge = (status: string) => {
    const variants: Record<string, "default" | "secondary" | "destructive"> = {
      healthy: "default",
      unhealthy: "destructive",
      unknown: "secondary"
    };
    
    return (
      <Badge variant={variants[status] || "secondary"} className="flex items-center gap-1">
        {getStatusIcon(status)}
        {status}
      </Badge>
    );
  };

  const getUptimeColor = (uptime: number) => {
    if (uptime >= 99) return "text-green-600";
    if (uptime >= 95) return "text-yellow-600";
    return "text-red-600";
  };

  if (loading) {
    return <div className="flex items-center justify-center p-8">Loading health data...</div>;
  }

  return (
    <div className="space-y-6">
      {/* Header with Refresh */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Model Health Overview</h2>
          <p className="text-muted-foreground">
            Last updated: {metrics?.last_updated ? new Date(metrics.last_updated).toLocaleString() : 'Never'}
          </p>
        </div>
        <Button onClick={handleRefresh} disabled={refreshing} variant="outline">
          <RefreshCw className={`w-4 h-4 mr-2 ${refreshing ? 'animate-spin' : ''}`} />
          Refresh
        </Button>
      </div>

      {/* Metrics Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Models</CardTitle>
            <Cpu className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{metrics?.total_models}</div>
            <div className="flex gap-2 text-xs text-muted-foreground">
              <span className="text-green-600">{metrics?.healthy_models} healthy</span>
              <span className="text-red-600">{metrics?.unhealthy_models} unhealthy</span>
            </div>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">System Uptime</CardTitle>
            <Activity className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">{metrics?.uptime_percentage}%</div>
            <Progress value={metrics?.uptime_percentage} className="h-2 mt-2" />
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Avg Latency</CardTitle>
            <Zap className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{metrics?.avg_latency}ms</div>
            <p className="text-xs text-muted-foreground">Across all models</p>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Health Score</CardTitle>
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">
              {metrics ? Math.round((metrics.healthy_models / metrics.total_models) * 100) : 0}%
            </div>
            <p className="text-xs text-muted-foreground">Models responding</p>
          </CardContent>
        </Card>
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Latency Trends (24h)</CardTitle>
            <CardDescription>Response times by provider</CardDescription>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={latencyData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="time" />
                <YAxis />
                <Tooltip />
                <Line type="monotone" dataKey="groq" stroke="#8884d8" strokeWidth={2} />
                <Line type="monotone" dataKey="bge_m3" stroke="#82ca9d" strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Request Volume (24h)</CardTitle>
            <CardDescription>Total requests per hour</CardDescription>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={requestVolumeData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="hour" />
                <YAxis />
                <Tooltip />
                <Bar dataKey="requests" fill="#8884d8" />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>

      {/* Individual Model Health */}
      <Card>
        <CardHeader>
          <CardTitle>Individual Model Status</CardTitle>
          <CardDescription>Detailed health information for each model</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {modelHealth.map((model) => (
              <div key={model.model_id} className="flex items-center justify-between p-4 border rounded-lg">
                <div className="flex items-center gap-4">
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="font-medium">{model.name}</h3>
                      <Badge variant="outline">{model.provider}</Badge>
                    </div>
                    <p className="text-sm text-muted-foreground">{model.model_id}</p>
                    {model.error_message && (
                      <p className="text-xs text-red-600 mt-1">{model.error_message}</p>
                    )}
                  </div>
                </div>
                
                <div className="flex items-center gap-6 text-sm">
                  <div className="text-center">
                    <div className="font-medium">{model.latency_ms}ms</div>
                    <div className="text-muted-foreground">Latency</div>
                  </div>
                  
                  <div className="text-center">
                    <div className="font-medium">{model.success_rate}%</div>
                    <div className="text-muted-foreground">Success Rate</div>
                  </div>
                  
                  <div className="text-center">
                    <div className={`font-medium ${getUptimeColor(model.uptime_24h)}`}>
                      {model.uptime_24h}%
                    </div>
                    <div className="text-muted-foreground">24h Uptime</div>
                  </div>
                  
                  <div className="text-center">
                    {getStatusBadge(model.health_status)}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}