'use client';

import * as React from 'react';
import { Check } from 'lucide-react';
import { cn } from '@/lib/utils';

interface CheckboxProps {
  checked?: boolean;
  onCheckedChange?: (checked: boolean) => void;
  disabled?: boolean;
  className?: string;
  id?: string;
}

const Checkbox = React.forwardRef<
  HTMLInputElement,
  CheckboxProps
>(({ checked = false, onCheckedChange, disabled = false, className, id }, ref) => {
  return (
    <div className="relative inline-flex items-center">
      <input
        ref={ref}
        type="checkbox"
        id={id}
        checked={checked}
        onChange={(e) => onCheckedChange?.(e.target.checked)}
        disabled={disabled}
        className="sr-only"
      />
      <div
        className={cn(
          'w-4 h-4 rounded border border-gt-gray-300 bg-gt-white transition-colors duration-200 cursor-pointer flex items-center justify-center',
          checked && 'bg-gt-green border-gt-green',
          disabled && 'opacity-50 cursor-not-allowed',
          className
        )}
        onClick={() => !disabled && onCheckedChange?.(!checked)}
      >
        {checked && (
          <Check className="w-3 h-3 text-white" />
        )}
      </div>
    </div>
  );
});

Checkbox.displayName = 'Checkbox';

export { Checkbox };