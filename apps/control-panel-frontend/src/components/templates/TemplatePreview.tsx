import { Badge } from '@/components/ui/badge';
import { Bot, Database, Cpu } from 'lucide-react';

interface Template {
  id: number;
  name: string;
  resource_counts: {
    models: number;
    agents: number;
    datasets: number;
  };
}

interface TemplatePreviewProps {
  template: Template;
}

export function TemplatePreview({ template }: TemplatePreviewProps) {
  const { models, agents, datasets } = template.resource_counts;

  return (
    <div className="space-y-2">
      <div className="text-sm text-muted-foreground">This template includes:</div>
      <div className="flex flex-wrap gap-2">
        {models > 0 && (
          <Badge variant="secondary" className="flex items-center gap-1">
            <Cpu className="h-3 w-3" />
            {models} Model{models > 1 ? 's' : ''}
          </Badge>
        )}
        {agents > 0 && (
          <Badge variant="secondary" className="flex items-center gap-1">
            <Bot className="h-3 w-3" />
            {agents} Agent{agents > 1 ? 's' : ''}
          </Badge>
        )}
        {datasets > 0 && (
          <Badge variant="secondary" className="flex items-center gap-1">
            <Database className="h-3 w-3" />
            {datasets} Dataset{datasets > 1 ? 's' : ''}
          </Badge>
        )}
        {models === 0 && agents === 0 && datasets === 0 && (
          <Badge variant="outline">Empty Template</Badge>
        )}
      </div>
    </div>
  );
}