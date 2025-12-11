import { useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Loader2, AlertCircle } from 'lucide-react';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { TemplatePreview } from './TemplatePreview';

interface Template {
  id: number;
  name: string;
  description: string;
  resource_counts: {
    models: number;
    agents: number;
    datasets: number;
  };
}

interface ApplyTemplateModalProps {
  open: boolean;
  onClose: () => void;
  template: Template;
  onSuccess: () => void;
}

export function ApplyTemplateModal({
  open,
  onClose,
  template,
  onSuccess
}: ApplyTemplateModalProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleApply = async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await fetch('/api/v1/templates/apply', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          template_id: template.id,
          tenant_id: 1
        })
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Failed to apply template');
      }

      const result = await response.json();
      console.log('Template applied:', result);
      onSuccess();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Apply Template: {template.name}</DialogTitle>
          <DialogDescription>
            This will add the following resources to your tenant
          </DialogDescription>
        </DialogHeader>

        <div className="py-4">
          <TemplatePreview template={template} />
        </div>

        {error && (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={loading}>
            Cancel
          </Button>
          <Button onClick={handleApply} disabled={loading}>
            {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Apply Template
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}