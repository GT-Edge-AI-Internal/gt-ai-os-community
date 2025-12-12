import * as React from "react"
import toast from 'react-hot-toast'

interface ToastOptions {
  title?: string;
  description?: string;
  variant?: "default" | "destructive";
}

// Simple wrapper around react-hot-toast to match the expected interface
export function useToast() {
  const toastFunction = (options: ToastOptions | string) => {
    if (typeof options === 'string') {
      return toast(options);
    }
    
    const { title, description, variant } = options;
    const message = title && description ? `${title}: ${description}` : title || description || '';
    
    if (variant === 'destructive') {
      return toast.error(message);
    } else {
      return toast.success(message);
    }
  };

  return {
    toast: toastFunction
  }
}