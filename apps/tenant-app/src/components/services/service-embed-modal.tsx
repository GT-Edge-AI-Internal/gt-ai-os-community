'use client';

import { useState, useEffect, useRef } from 'react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { cn, formatDateTime } from '@/lib/utils';
import { externalServicesAPI, ServiceInstance, EmbedConfig } from '@/lib/api/external-services';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  ExternalLink,
  Maximize2,
  Minimize2,
  RefreshCw,
  Shield,
  BookOpen,
  Monitor,
  Server,
  Activity,
  AlertCircle,
  Loader2
} from 'lucide-react';

interface ServiceEmbedModalProps {
  service: ServiceInstance;
  onClose: () => void;
}

export function ServiceEmbedModal({ service, onClose }: ServiceEmbedModalProps) {
  const [embedConfig, setEmbedConfig] = useState<EmbedConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const iframeRef = useRef<HTMLIFrameElement>(null);

  useEffect(() => {
    loadEmbedConfig();
  }, [service.id]);

  const loadEmbedConfig = async () => {
    try {
      setLoading(true);
      setError(null);

      const embedConfig = await externalServicesAPI.getEmbedConfig(service.id);
      setEmbedConfig(embedConfig);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load service');
    } finally {
      setLoading(false);
    }
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    
    // Refresh the iframe
    if (iframeRef.current) {
      iframeRef.current.src = iframeRef.current.src;
    }
    
    // Simulate refresh delay
    await new Promise(resolve => setTimeout(resolve, 1000));
    setRefreshing(false);
  };

  const handleFullscreen = () => {
    setIsFullscreen(true);
  };

  const handleExitFullscreen = () => {
    setIsFullscreen(false);
  };

  const handleOpenExternal = () => {
    if (embedConfig) {
      window.open(embedConfig.iframe_url, '_blank');
    }
  };

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

  const getServiceTypeColor = (type: string) => {
    switch (type) {
      case 'ctfd':
        return 'bg-red-100 text-red-600';
      case 'canvas':
        return 'bg-blue-100 text-blue-600';
      case 'guacamole':
        return 'bg-green-100 text-green-600';
      default:
        return 'bg-gray-100 text-gray-600';
    }
  };

  if (loading) {
    return (
      <Dialog open={true} onOpenChange={onClose}>
        <DialogContent className="max-w-6xl max-h-[90vh]">
          <div className="flex flex-col items-center justify-center py-12">
            <Loader2 className="w-8 h-8 animate-spin text-gt-green mb-4" />
            <h3 className="text-lg font-medium mb-2">Loading Service</h3>
            <p className="text-gray-600 text-center">
              Setting up secure SSO access to {service.service_name}...
            </p>
          </div>
        </DialogContent>
      </Dialog>
    );
  }

  if (error) {
    return (
      <Dialog open={true} onOpenChange={onClose}>
        <DialogContent className="max-w-2xl">
          <div className="flex flex-col items-center justify-center py-12">
            <AlertCircle className="w-16 h-16 text-red-500 mb-4" />
            <h3 className="text-lg font-medium mb-2">Service Unavailable</h3>
            <p className="text-gray-600 text-center mb-4">{error}</p>
            <div className="flex space-x-3">
              <Button onClick={loadEmbedConfig} variant="secondary">
                <RefreshCw className="w-4 h-4 mr-2" />
                Retry
              </Button>
              <Button onClick={onClose}>Close</Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    );
  }

  return (
    <Dialog 
      open={true} 
      onOpenChange={onClose}
    >
      <DialogContent 
        className={cn(
          "transition-all duration-300",
          isFullscreen 
            ? "fixed inset-0 max-w-none max-h-none w-screen h-screen rounded-none" 
            : "max-w-6xl max-h-[90vh] w-[90vw] h-[85vh]"
        )}
      >
        <DialogHeader>
          <div className="flex items-center justify-between flex-shrink-0 border-b pb-4">
            <div className="flex items-center space-x-3">
              <div className={cn(
                "w-10 h-10 rounded-lg flex items-center justify-center",
                getServiceTypeColor(service.service_type)
              )}>
                {getServiceIcon(service.service_type)}
              </div>
              <div>
                <DialogTitle>
                  <div className="text-lg">{service.service_name}</div>
                </DialogTitle>
                <div className="flex items-center space-x-2 mt-1">
                  <Badge className="bg-green-100 text-green-700 text-xs">
                    <Activity className="w-3 h-3 mr-1" />
                    {service.status}
                  </Badge>
                  <span className="text-sm text-gray-600 capitalize">
                    {service.service_type.replace('_', ' ')}
                  </span>
                </div>
              </div>
            </div>

            <div className="flex items-center space-x-2">
              <Button
                onClick={handleRefresh}
                variant="secondary"
                size="sm"
                disabled={refreshing}
              >
                <RefreshCw className={cn("w-4 h-4", refreshing && "animate-spin")} />
              </Button>
              
              <Button
                onClick={handleOpenExternal}
                variant="secondary"
                size="sm"
              >
                <ExternalLink className="w-4 h-4" />
              </Button>

              {!isFullscreen ? (
                <Button
                  onClick={handleFullscreen}
                  variant="secondary"
                  size="sm"
                >
                  <Maximize2 className="w-4 h-4" />
                </Button>
              ) : (
                <Button
                  onClick={handleExitFullscreen}
                  variant="secondary"
                  size="sm"
                >
                  <Minimize2 className="w-4 h-4" />
                </Button>
              )}
            </div>
          </div>
        </DialogHeader>

        <div className="flex-1 min-h-0">
          {embedConfig && (
            <iframe
              ref={iframeRef}
              src={embedConfig.iframe_url}
              className="w-full h-full border-0 rounded-lg"
              sandbox={embedConfig.sandbox_attributes.join(' ')}
              allow={embedConfig.security_policies.allow}
              referrerPolicy={embedConfig.security_policies.referrerpolicy as any}
              loading={embedConfig.security_policies.loading as any}
              title={`${service.service_name} - ${service.service_type}`}
            />
          )}
        </div>

        {/* Security Info Footer */}
        {embedConfig && (
          <div className="flex-shrink-0 border-t pt-3 mt-4">
            <div className="flex items-center justify-between text-xs text-gray-500">
              <div className="flex items-center space-x-4">
                <div className="flex items-center">
                  <Shield className="w-3 h-3 mr-1 text-green-600" />
                  SSO Enabled
                </div>
                <div>
                  Token expires: {formatDateTime(embedConfig.expires_at)}
                </div>
              </div>
              
              <div className="text-right">
                {service.endpoint_url}
              </div>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}