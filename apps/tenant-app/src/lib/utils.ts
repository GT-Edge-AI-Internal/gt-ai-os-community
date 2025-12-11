import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';
import { useEffect, useState } from 'react';

/**
 * Utility function for combining class names with Tailwind CSS merge support
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Custom hook for debouncing values (performance optimization)
 *
 * Use this to prevent expensive operations from running on every keystroke.
 * Example: Debounce search input to avoid filtering on every character typed.
 *
 * @param value The value to debounce
 * @param delay Delay in milliseconds (default: 300ms)
 * @returns Debounced value
 *
 * @example
 * const [searchQuery, setSearchQuery] = useState('');
 * const debouncedSearch = useDebouncedValue(searchQuery, 300);
 *
 * // Use debouncedSearch for filtering instead of searchQuery
 * const filtered = items.filter(item => item.name.includes(debouncedSearch));
 */
export function useDebouncedValue<T>(value: T, delay: number = 300): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);

  useEffect(() => {
    // Set up a timer to update the debounced value after the delay
    const handler = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    // Clean up the timer if value changes before delay completes
    return () => {
      clearTimeout(handler);
    };
  }, [value, delay]);

  return debouncedValue;
}

/**
 * Format date for display in the UI (uses browser locale)
 */
export function formatDate(date: string | Date): string {
  const d = typeof date === 'string' ? new Date(date) : date;
  return d.toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

/**
 * Format date and time for display (uses browser locale)
 */
export function formatDateTime(date: string | Date): string {
  const d = typeof date === 'string' ? new Date(date) : date;
  return d.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

/**
 * Format time only for display (uses browser locale)
 */
export function formatTime(date: string | Date): string {
  const d = typeof date === 'string' ? new Date(date) : date;
  return d.toLocaleTimeString(undefined, {
    hour: '2-digit',
    minute: '2-digit',
  });
}

/**
 * Format date only (no time) for display (uses browser locale)
 */
export function formatDateOnly(date: string | Date): string {
  const d = typeof date === 'string' ? new Date(date) : date;
  return d.toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

/**
 * Format date for relative display (e.g., "2 hours ago")
 */
export function formatRelativeTime(date: string | Date): string {
  const d = typeof date === 'string' ? new Date(date) : date;
  const now = new Date();
  const diffInSeconds = Math.floor((now.getTime() - d.getTime()) / 1000);

  if (diffInSeconds < 60) {
    return 'just now';
  }

  const diffInMinutes = Math.floor(diffInSeconds / 60);
  if (diffInMinutes < 60) {
    return `${diffInMinutes}m ago`;
  }

  const diffInHours = Math.floor(diffInMinutes / 60);
  if (diffInHours < 24) {
    return `${diffInHours}h ago`;
  }

  const diffInDays = Math.floor(diffInHours / 24);
  if (diffInDays < 7) {
    return `${diffInDays}d ago`;
  }

  const diffInWeeks = Math.floor(diffInDays / 7);
  if (diffInWeeks < 4) {
    return `${diffInWeeks}w ago`;
  }

  const diffInMonths = Math.floor(diffInDays / 30);
  if (diffInMonths < 12) {
    return `${diffInMonths}mo ago`;
  }

  const diffInYears = Math.floor(diffInDays / 365);
  return `${diffInYears}y ago`;
}

/**
 * Format file size for display
 */
export function formatFileSize(bytes: number): string {
  const units = ['B', 'KiB', 'MiB', 'GiB'];
  let size = bytes;
  let unitIndex = 0;

  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex++;
  }

  return `${size.toFixed(unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`;
}

/**
 * Format storage size in megabytes for display
 */
export function formatStorageSize(mb: number): string {
  if (mb >= 1024 * 1024) return `${(mb / (1024 * 1024)).toFixed(2)} TiB`;
  if (mb >= 1024) return `${(mb / 1024).toFixed(2)} GiB`;
  return `${mb.toFixed(2)} MiB`;
}

/**
 * Format token count for display
 */
export function formatTokenCount(tokens: number): string {
  if (tokens < 1000) {
    return tokens.toString();
  }

  if (tokens < 1000000) {
    return `${(tokens / 1000).toFixed(1)}K`;
  }

  return `${(tokens / 1000000).toFixed(1)}M`;
}

/**
 * Format cost in cents to dollars (uses browser locale)
 */
export function formatCost(cents: number): string {
  const dollars = cents / 100;
  return new Intl.NumberFormat(undefined, {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: dollars < 1 ? 3 : 2,
  }).format(dollars);
}

/**
 * Generate a random UUID v4
 */
export function generateUUID(): string {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
    const r = Math.random() * 16 | 0;
    const v = c == 'x' ? r : (r & 0x3 | 0x8);
    return v.toString(16);
  });
}

/**
 * Truncate text to a specified length
 */
export function truncateText(text: string, maxLength: number): string {
  if (text.length <= maxLength) {
    return text;
  }
  return text.slice(0, maxLength) + '...';
}

/**
 * Debounce function
 */
export function debounce<T extends (...args: any[]) => any>(
  func: T,
  wait: number
): (...args: Parameters<T>) => void {
  let timeout: NodeJS.Timeout;
  return (...args: Parameters<T>) => {
    clearTimeout(timeout);
    timeout = setTimeout(() => func(...args), wait);
  };
}

/**
 * Throttle function
 */
export function throttle<T extends (...args: any[]) => any>(
  func: T,
  limit: number
): (...args: Parameters<T>) => void {
  let inThrottle: boolean;
  return (...args: Parameters<T>) => {
    if (!inThrottle) {
      func(...args);
      inThrottle = true;
      setTimeout(() => inThrottle = false, limit);
    }
  };
}

/**
 * Clean model names by removing provider prefixes like "groq/"
 */
export function cleanModelName(name: string): string {
  return name.replace(/^(groq|openai|anthropic)\//, '');
}

/**
 * Check if a string is a valid email
 */
export function isValidEmail(email: string): boolean {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return emailRegex.test(email);
}

/**
 * Get initials from a full name
 */
export function getInitials(name: string): string {
  if (!name) return '';
  
  return name
    .split(' ')
    .map(word => word.charAt(0).toUpperCase())
    .slice(0, 2)
    .join('');
}

/**
 * Check if the current environment is development
 */
export function isDevelopment(): boolean {
  return process.env.NODE_ENV === 'development';
}

/**
 * Get the base API URL
 */
export function getApiUrl(): string {
  // Use relative path for browser - Next.js will proxy to tenant-backend via Docker network
  if (typeof window !== 'undefined') {
    return '';
  }
  // Server-side uses internal Docker network URL
  return process.env.INTERNAL_BACKEND_URL || 'http://tenant-backend:8000';
}

/**
 * Get WebSocket URL
 * Returns current window origin to route Socket.IO through Next.js proxy.
 * Next.js rewrites /socket.io/* to backend via INTERNAL_BACKEND_URL.
 * This ensures Socket.IO works through Cloudflare tunnel (port 3002 only).
 */
export function getWebSocketUrl(): string {
  if (typeof window !== 'undefined') {
    // Use current window origin (no port override)
    // Next.js will proxy /socket.io/* to backend via rewrite rules
    return window.location.origin;
  }
  // Server-side fallback (not used for Socket.IO client connections)
  return 'ws://tenant-backend:8000';
}

/**
 * Handle API errors consistently
 */
export function handleApiError(error: any): string {
  if (error?.response?.data?.message) {
    return error.response.data.message;
  }
  
  if (error?.message) {
    return error.message;
  }
  
  return 'An unexpected error occurred. Please try again.';
}

/**
 * Generate a conversation title from the first message
 */
export function generateConversationTitle(firstMessage: string): string {
  // Remove common prefixes
  const cleaned = firstMessage
    .replace(/^(hi|hello|hey|can you|could you|please|i need|help me|how do|what is|what are)/i, '')
    .trim();
  
  // Truncate to reasonable length
  const truncated = truncateText(cleaned, 50);
  
  // Return cleaned title or fallback
  return truncated || 'New Conversation';
}

/**
 * Copy text to clipboard
 */
export async function copyToClipboard(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch (error) {
    console.error('Failed to copy to clipboard:', error);
    return false;
  }
}

/**
 * Download a file with specified content
 */
export function downloadFile(content: string, filename: string, mimeType: string = 'text/plain'): void {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}