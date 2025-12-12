'use client';

import React from 'react';
import { Button } from '@/components/ui/button';
import { Sparkles } from 'lucide-react';

interface EasyButtonsProps {
  prompts: string[];
  onPromptClick: (prompt: string) => void;
  className?: string;
}

export function EasyButtons({ prompts, onPromptClick, className }: EasyButtonsProps) {
  if (!prompts || prompts.length === 0) {
    return null;
  }

  return (
    <div className={className}>
      <div className="flex items-center gap-2 mb-2">
        <Sparkles className="w-4 h-4 text-gray-500" />
        <span className="text-sm font-medium text-gray-700">Quick Prompts</span>
      </div>
      <div className="flex flex-wrap gap-2">
        {prompts.map((prompt, index) => (
          <Button
            key={index}
            variant="outline"
            size="sm"
            onClick={() => onPromptClick(prompt)}
            className="text-sm hover:bg-gt-green/10 hover:border-gt-green hover:text-gt-green transition-colors"
          >
            {prompt}
          </Button>
        ))}
      </div>
    </div>
  );
}