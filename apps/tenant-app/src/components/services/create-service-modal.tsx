'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { 
  Shield, 
  BookOpen, 
  Monitor, 
  Server,
  Clock,
  Cpu,
  HardDrive,
  Users,
  CheckCircle2
} from 'lucide-react';

interface ServiceType {
  type: string;
  name: string;
  description: string;
  category: string;
  features: string[];
  resource_requirements: {
    cpu: string;
    memory: string;
    storage: string;
  };
  estimated_startup_time: string;
  sso_supported: boolean;
}

interface CreateServiceModalProps {
  serviceTypes: ServiceType[];
  onClose: () => void;
  onCreate: (serviceType: string, serviceName: string, config: any) => void;
}

export function CreateServiceModal({ serviceTypes, onClose, onCreate }: CreateServiceModalProps) {
  const [selectedType, setSelectedType] = useState<string>('');
  const [serviceName, setServiceName] = useState<string>('');
  const [description, setDescription] = useState<string>('');
  const [isCreating, setIsCreating] = useState(false);

  const selectedServiceType = serviceTypes.find(type => type.type === selectedType);

  const handleCreate = async () => {
    if (!selectedType || !serviceName.trim()) return;

    setIsCreating(true);
    try {
      await onCreate(selectedType, serviceName, {
        description: description.trim() || undefined,
        auto_start: true
      });
    } finally {
      setIsCreating(false);
    }
  };

  const getServiceIcon = (type: string) => {
    switch (type) {
      case 'ctfd':
        return <Shield className="w-6 h-6" />;
      case 'canvas':
        return <BookOpen className="w-6 h-6" />;
      case 'guacamole':
        return <Monitor className="w-6 h-6" />;
      default:
        return <Server className="w-6 h-6" />;
    }
  };

  const getCategoryColor = (category: string) => {
    switch (category) {
      case 'cybersecurity':
        return 'text-red-600 bg-red-100 border-red-200';
      case 'education':
        return 'text-blue-600 bg-blue-100 border-blue-200';
      case 'remote_access':
        return 'text-green-600 bg-green-100 border-green-200';
      default:
        return 'text-gray-600 bg-gray-100 border-gray-200';
    }
  };

  return (
    <Dialog open={true} onOpenChange={onClose}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Create New Service</DialogTitle>
          <DialogDescription>
            Deploy an external service instance with secure SSO integration
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6">
          {/* Service Type Selection */}
          <div className="space-y-4">
            <Label className="text-base font-medium">Service Type</Label>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {serviceTypes.map((type) => (
                <Card
                  key={type.type}
                  className={cn(
                    "cursor-pointer border-2 transition-all hover:shadow-md",
                    selectedType === type.type 
                      ? "border-gt-green bg-gt-green/5" 
                      : "border-gray-200 hover:border-gray-300"
                  )}
                  onClick={() => setSelectedType(type.type)}
                >
                  <CardHeader className="pb-3">
                    <div className="flex items-center space-x-3">
                      <div className={cn(
                        "w-12 h-12 rounded-lg flex items-center justify-center",
                        getCategoryColor(type.category)
                      )}>
                        {getServiceIcon(type.type)}
                      </div>
                      <div className="flex-1">
                        <CardTitle className="text-lg">{type.name}</CardTitle>
                        <Badge variant="secondary" className="text-xs">
                          {type.category}
                        </Badge>
                      </div>
                      {selectedType === type.type && (
                        <CheckCircle2 className="w-5 h-5 text-gt-green" />
                      )}
                    </div>
                  </CardHeader>
                  <CardContent className="pt-0">
                    <p className="text-sm text-gray-600 mb-3 line-clamp-2">
                      {type.description}
                    </p>
                    
                    <div className="space-y-2">
                      <div className="flex items-center justify-between text-xs text-gray-600">
                        <div className="flex items-center">
                          <Cpu className="w-3 h-3 mr-1" />
                          {type.resource_requirements.cpu}
                        </div>
                        <div className="flex items-center">
                          <HardDrive className="w-3 h-3 mr-1" />
                          {type.resource_requirements.storage}
                        </div>
                      </div>
                      <div className="flex items-center justify-between text-xs text-gray-600">
                        <div className="flex items-center">
                          <Clock className="w-3 h-3 mr-1" />
                          {type.estimated_startup_time}
                        </div>
                        <div className="flex items-center">
                          <Users className="w-3 h-3 mr-1" />
                          SSO: {type.sso_supported ? '✓' : '✗'}
                        </div>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>

          {/* Service Configuration */}
          {selectedType && (
            <div className="space-y-4 border-t pt-6">
              <Label className="text-base font-medium">Service Configuration</Label>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="serviceName">Service Name *</Label>
                  <Input
                    id="serviceName"
                    placeholder={`My ${selectedServiceType?.name}`}
                    value={serviceName}
                    onChange={(value) => setServiceName(value)}
                  />
                  <p className="text-xs text-gray-500">
                    A human-readable name for this service instance
                  </p>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="description">Description (Optional)</Label>
                  <Input
                    id="description"
                    placeholder="Brief description of this service..."
                    value={description}
                    onChange={(value) => setDescription(value)}
                  />
                </div>
              </div>

              {/* Service Details Preview */}
              {selectedServiceType && (
                <Card className="bg-gray-50">
                  <CardHeader className="pb-3">
                    <CardTitle className="text-base flex items-center">
                      <div className={cn(
                        "w-8 h-8 rounded flex items-center justify-center mr-3",
                        getCategoryColor(selectedServiceType.category)
                      )}>
                        {getServiceIcon(selectedServiceType.type)}
                      </div>
                      {selectedServiceType.name} Features
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div>
                        <h4 className="text-sm font-medium mb-2">Key Features</h4>
                        <ul className="text-sm text-gray-600 space-y-1">
                          {selectedServiceType.features.slice(0, 4).map((feature, index) => (
                            <li key={index} className="flex items-center">
                              <CheckCircle2 className="w-3 h-3 text-gt-green mr-2 flex-shrink-0" />
                              {feature}
                            </li>
                          ))}
                        </ul>
                      </div>
                      
                      <div>
                        <h4 className="text-sm font-medium mb-2">Resource Requirements</h4>
                        <div className="space-y-1 text-sm text-gray-600">
                          <div className="flex justify-between">
                            <span>CPU:</span>
                            <span className="font-medium">{selectedServiceType.resource_requirements.cpu}</span>
                          </div>
                          <div className="flex justify-between">
                            <span>Memory:</span>
                            <span className="font-medium">{selectedServiceType.resource_requirements.memory}</span>
                          </div>
                          <div className="flex justify-between">
                            <span>Storage:</span>
                            <span className="font-medium">{selectedServiceType.resource_requirements.storage}</span>
                          </div>
                          <div className="flex justify-between">
                            <span>Startup Time:</span>
                            <span className="font-medium">{selectedServiceType.estimated_startup_time}</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              )}
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="secondary" onClick={onClose} disabled={isCreating}>
            Cancel
          </Button>
          <Button
            onClick={handleCreate}
            disabled={!selectedType || !serviceName.trim() || isCreating}
            className="bg-gt-green hover:bg-gt-green/90"
          >
            {isCreating ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent mr-2" />
                Creating...
              </>
            ) : (
              `Create ${selectedServiceType?.name || 'Service'}`
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}