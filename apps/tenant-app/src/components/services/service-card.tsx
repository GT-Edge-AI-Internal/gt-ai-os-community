'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { cn, formatDateOnly } from '@/lib/utils';
import {
  Server,
  ExternalLink,
  Settings,
  Trash2,
  Users,
  Shield,
  BookOpen,
  Monitor,
  Play,
  Square,
  Activity,
  Clock
} from 'lucide-react';
import { ServiceInstance } from '@/lib/api/external-services';

interface ServiceCardProps {
  service: ServiceInstance;
  onLaunch: (service: ServiceInstance) => void;
  onDelete: (serviceId: string) => void;
  onSettings: (serviceId: string) => void;
}

export function ServiceCard({ service, onLaunch, onDelete, onSettings }: ServiceCardProps) {
  const getServiceIcon = (type: string) => {
    switch (type) {
      case 'ctfd':
        return <Shield className="w-5 h-5" />;
      case 'canvas':
        return <BookOpen className="w-5 h-5" />;
      case 'guacamole':
        return <Monitor className="w-5 h-5" />;
      default:
        return <Server className="w-5 h-5" />;
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'running':
        return (
          <Badge className="bg-green-100 text-green-700 border-green-200">
            <Activity className="w-3 h-3 mr-1" />
            Running
          </Badge>
        );
      case 'stopped':
        return (
          <Badge className="bg-gray-100 text-gray-700 border-gray-200">
            <Square className="w-3 h-3 mr-1" />
            Stopped
          </Badge>
        );
      case 'starting':
        return (
          <Badge className="bg-blue-100 text-blue-700 border-blue-200">
            <Play className="w-3 h-3 mr-1" />
            Starting
          </Badge>
        );
      case 'error':
        return (
          <Badge className="bg-red-100 text-red-700 border-red-200">
            Error
          </Badge>
        );
      default:
        return (
          <Badge variant="secondary">
            {status}
          </Badge>
        );
    }
  };

  const getHealthBadge = (health: string) => {
    switch (health) {
      case 'healthy':
        return (
          <div className="flex items-center text-xs text-green-600">
            <div className="w-2 h-2 bg-green-500 rounded-full mr-1" />
            Healthy
          </div>
        );
      case 'unhealthy':
        return (
          <div className="flex items-center text-xs text-red-600">
            <div className="w-2 h-2 bg-red-500 rounded-full mr-1" />
            Unhealthy
          </div>
        );
      default:
        return (
          <div className="flex items-center text-xs text-gray-600">
            <div className="w-2 h-2 bg-gray-400 rounded-full mr-1" />
            Unknown
          </div>
        );
    }
  };

  const getLastAccessed = () => {
    if (!service.last_accessed) return 'Never';
    
    const lastAccessed = new Date(service.last_accessed);
    const now = new Date();
    const diffMs = now.getTime() - lastAccessed.getTime();
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    const diffDays = Math.floor(diffHours / 24);

    if (diffHours < 1) return 'Just now';
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return formatDateOnly(lastAccessed);
  };

  return (
    <Card className="hover:shadow-lg transition-shadow duration-200">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="flex items-center space-x-3">
            <div className={cn(
              "w-12 h-12 rounded-lg flex items-center justify-center",
              service.service_type === 'ctfd' && "bg-red-100 text-red-600",
              service.service_type === 'canvas' && "bg-blue-100 text-blue-600",
              service.service_type === 'guacamole' && "bg-green-100 text-green-600",
              !['ctfd', 'canvas', 'guacamole'].includes(service.service_type) && "bg-gray-100 text-gray-600"
            )}>
              {getServiceIcon(service.service_type)}
            </div>
            <div>
              <CardTitle className="text-lg">{service.service_name}</CardTitle>
              <p className="text-sm text-gray-600 capitalize">
                {service.service_type.replace('_', ' ')}
              </p>
            </div>
          </div>
          <div className="flex items-center space-x-2">
            {getStatusBadge(service.status)}
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Description */}
        <p className="text-sm text-gray-600 line-clamp-2">
          {service.description}
        </p>

        {/* Health & Users Info */}
        <div className="flex items-center justify-between text-sm">
          <div className="flex items-center space-x-4">
            {getHealthBadge(service.health_status)}
            <div className="flex items-center text-gray-600">
              <Users className="w-3 h-3 mr-1" />
              {service.allowed_users.length} {service.allowed_users.length === 1 ? 'user' : 'users'}
            </div>
          </div>
          <div className="flex items-center text-gray-500">
            <Clock className="w-3 h-3 mr-1" />
            {getLastAccessed()}
          </div>
        </div>

        {/* Access Level */}
        <div className="flex items-center justify-between">
          <Badge
            variant="secondary"
            className={cn(
              "text-xs",
              service.access_level === 'private' && "border-blue-200 text-blue-700",
              service.access_level === 'team' && "border-blue-200 text-blue-700",
              service.access_level === 'public' && "border-green-200 text-green-700"
            )}
          >
            {service.access_level}
          </Badge>
          
          <div className="text-xs text-gray-500">
            Created {formatDateOnly(service.created_at)}
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center space-x-2 pt-2 border-t">
          <Button
            onClick={() => onLaunch(service)}
            disabled={service.status !== 'running'}
            className="flex-1 bg-gt-green hover:bg-gt-green/90 disabled:opacity-50"
            size="sm"
          >
            <ExternalLink className="w-3 h-3 mr-2" />
            Launch
          </Button>
          
          <Button
            onClick={() => onSettings(service.id)}
            variant="secondary"
            size="sm"
            className="px-3"
          >
            <Settings className="w-3 h-3" />
          </Button>
          
          <Button
            onClick={() => {
              if (window.confirm(`Are you sure you want to delete ${service.service_name}?`)) {
                onDelete(service.id);
              }
            }}
            variant="secondary"
            size="sm"
            className="px-3 text-red-600 border-red-200 hover:bg-red-50"
          >
            <Trash2 className="w-3 h-3" />
          </Button>
        </div>

        {/* Endpoint URL (for reference) */}
        <div className="text-xs text-gray-500 font-mono bg-gray-50 p-2 rounded border truncate">
          {service.endpoint_url}
        </div>
      </CardContent>
    </Card>
  );
}