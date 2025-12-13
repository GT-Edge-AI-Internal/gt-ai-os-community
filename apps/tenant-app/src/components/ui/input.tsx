import { forwardRef } from 'react';
import { X } from 'lucide-react';
import { cn } from '@/lib/utils';
import { InputProps } from '@/types';

const Input = forwardRef<HTMLInputElement, InputProps & Omit<React.InputHTMLAttributes<HTMLInputElement>, 'onChange'> & { clearable?: boolean }>(
  ({
    label,
    error,
    className,
    type = 'text',
    onChange,
    clearable = false,
    value,
    ...props
  }, ref) => {
    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      if (onChange) {
        onChange(e.target.value);
      }
    };

    const handleClear = () => {
      if (onChange) {
        onChange('');
      }
    };

    const inputElement = (
      <input
        ref={ref}
        type={type}
        value={value}
        className={cn(
          'block w-full px-3 py-2 border border-gt-gray-300 rounded-lg shadow-sm placeholder-gt-gray-400',
          'bg-gt-white text-gt-gray-900',
          'focus:outline-none focus:ring-2 focus:ring-gt-green focus:border-gt-green',
          'disabled:bg-gt-gray-50 disabled:text-gt-gray-500 disabled:cursor-not-allowed',
          'transition-colors duration-150',
          {
            'border-red-300 focus:border-red-500 focus:ring-red-500': error,
            'pr-8': clearable,
          },
          className
        )}
        onChange={handleChange}
        {...props}
      />
    );

    return (
      <div className="w-full">
        {label && (
          <label className="block text-sm font-medium text-gt-gray-700 mb-2">
            {label}
            {props.required && <span className="text-red-500 ml-1">*</span>}
          </label>
        )}
        {clearable ? (
          <div className="relative">
            {inputElement}
            {value && (
              <button
                type="button"
                onClick={handleClear}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-gt-gray-400 hover:text-gt-gray-600 transition-colors"
                tabIndex={-1}
              >
                <X className="w-4 h-4" />
              </button>
            )}
          </div>
        ) : (
          inputElement
        )}
        {error && (
          <p className="mt-2 text-sm text-red-600" role="alert">
            {error}
          </p>
        )}
      </div>
    );
  }
);

Input.displayName = 'Input';

const Textarea = forwardRef<HTMLTextAreaElement, InputProps & Omit<React.TextareaHTMLAttributes<HTMLTextAreaElement>, 'onChange'> & { resizable?: boolean }>(
  ({
    label,
    error,
    className,
    onChange,
    resizable = false,
    ...props
  }, ref) => {
    const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
      if (onChange) {
        onChange(e.target.value);
      }
    };

    return (
      <div className="w-full">
        {label && (
          <label className="block text-sm font-medium text-gt-gray-700 mb-2">
            {label}
            {props.required && <span className="text-red-500 ml-1">*</span>}
          </label>
        )}
        <textarea
          ref={ref}
          className={cn(
            'block w-full px-3 py-2 border border-gt-gray-300 rounded-lg shadow-sm placeholder-gt-gray-400',
            'bg-gt-white text-gt-gray-900',
            'focus:outline-none focus:ring-2 focus:ring-gt-green focus:border-gt-green',
            'disabled:bg-gt-gray-50 disabled:text-gt-gray-500 disabled:cursor-not-allowed',
            'transition-colors duration-150',
            resizable ? 'resize-y' : 'resize-none',
            {
              'border-red-300 focus:border-red-500 focus:ring-red-500': error,
            },
            className
          )}
          onChange={handleChange}
          {...props}
        />
        {error && (
          <p className="mt-2 text-sm text-red-600" role="alert">
            {error}
          </p>
        )}
      </div>
    );
  }
);

Textarea.displayName = 'Textarea';

export { Input, Textarea };