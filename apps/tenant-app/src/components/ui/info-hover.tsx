'use client';

import { Info } from 'lucide-react';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';

interface InfoHoverProps {
  content: string;
}

export function InfoHover({ content }: InfoHoverProps) {
  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            className="inline-flex items-center"
            aria-label="More information"
          >
            <Info className="w-4 h-4 text-gray-400 cursor-help" />
          </button>
        </TooltipTrigger>
        <TooltipContent className="w-80" role="tooltip">
          <p className="text-sm">{content}</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}