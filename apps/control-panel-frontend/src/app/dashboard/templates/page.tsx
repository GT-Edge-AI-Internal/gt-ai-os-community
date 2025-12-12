"use client";

import { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  FileText,
  Download,
  Upload,
  Trash2,
  Plus,
  Loader2,
  CheckCircle
} from 'lucide-react';
import { useToast } from '@/components/ui/use-toast';
import { TemplatePreview } from '@/components/templates/TemplatePreview';
import { ApplyTemplateModal } from '@/components/templates/ApplyTemplateModal';
import { ExportTemplateModal } from '@/components/templates/ExportTemplateModal';

interface Template {
  id: number;
  name: string;
  description: string;
  is_default: boolean;
  resource_counts: {
    models: number;
    agents: number;
    datasets: number;
  };
  created_at: string;
}

export default function TemplatesPage() {
  const { toast } = useToast();
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedTemplate, setSelectedTemplate] = useState<Template | null>(null);
  const [showApplyModal, setShowApplyModal] = useState(false);
  const [showExportModal, setShowExportModal] = useState(false);

  useEffect(() => {
    fetchTemplates();
  }, []);

  const fetchTemplates = async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/v1/templates/');
      if (!response.ok) throw new Error('Failed to fetch templates');

      const data = await response.json();
      setTemplates(data);
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to load templates",
        variant: "destructive"
      });
    } finally {
      setLoading(false);
    }
  };

  const handleApplyTemplate = (template: Template) => {
    setSelectedTemplate(template);
    setShowApplyModal(true);
  };

  const handleDeleteTemplate = async (templateId: number, templateName: string) => {
    if (!confirm(`Are you sure you want to delete template "${templateName}"?`)) {
      return;
    }

    try {
      const response = await fetch(`/api/v1/templates/${templateId}`, {
        method: 'DELETE'
      });

      if (!response.ok) throw new Error('Failed to delete template');

      toast({
        title: "Success",
        description: `Template "${templateName}" deleted successfully`
      });

      fetchTemplates();
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to delete template",
        variant: "destructive"
      });
    }
  };

  const onApplySuccess = () => {
    setShowApplyModal(false);
    setSelectedTemplate(null);
    toast({
      title: "Success",
      description: "Template applied successfully"
    });
  };

  const onExportSuccess = () => {
    setShowExportModal(false);
    fetchTemplates();
    toast({
      title: "Success",
      description: "Template exported successfully"
    });
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">Tenant Templates</h1>
          <p className="text-muted-foreground mt-1">
            Manage and apply configuration templates to tenants
          </p>
        </div>
        <Button onClick={() => setShowExportModal(true)}>
          <Plus className="h-4 w-4 mr-2" />
          Export Current Tenant
        </Button>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin" />
        </div>
      ) : templates.length === 0 ? (
        <Card>
          <CardContent className="py-12">
            <div className="text-center text-muted-foreground">
              <FileText className="h-12 w-12 mx-auto mb-4 opacity-50" />
              <p className="text-lg">No templates found</p>
              <p className="text-sm mt-1">Export your current tenant to create a template</p>
            </div>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {templates.map((template) => (
            <Card key={template.id} className="hover:shadow-lg transition-shadow">
              <CardHeader>
                <div className="flex justify-between items-start">
                  <div>
                    <CardTitle className="flex items-center gap-2">
                      {template.name}
                      {template.is_default && (
                        <Badge variant="default">Default</Badge>
                      )}
                    </CardTitle>
                    <CardDescription className="mt-1">
                      {template.description || 'No description'}
                    </CardDescription>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <TemplatePreview template={template} />

                <div className="flex gap-2">
                  <Button
                    onClick={() => handleApplyTemplate(template)}
                    className="flex-1"
                  >
                    <Upload className="h-4 w-4 mr-2" />
                    Apply
                  </Button>
                  {!template.is_default && (
                    <Button
                      variant="outline"
                      size="icon"
                      onClick={() => handleDeleteTemplate(template.id, template.name)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {selectedTemplate && (
        <ApplyTemplateModal
          open={showApplyModal}
          onClose={() => {
            setShowApplyModal(false);
            setSelectedTemplate(null);
          }}
          template={selectedTemplate}
          onSuccess={onApplySuccess}
        />
      )}

      <ExportTemplateModal
        open={showExportModal}
        onClose={() => setShowExportModal(false)}
        onSuccess={onExportSuccess}
      />
    </div>
  );
}