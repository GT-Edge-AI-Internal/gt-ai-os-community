'use client';

import * as React from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';
import { cn } from '@/lib/utils';

interface SheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  children: React.ReactNode;
}

export function Sheet({ open, onOpenChange, children }: SheetProps) {
  const [mounted, setMounted] = React.useState(false);

  React.useEffect(() => {
    setMounted(true);
    return () => setMounted(false);
  }, []);

  React.useEffect(() => {
    if (open) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = 'unset';
    }
    return () => {
      document.body.style.overflow = 'unset';
    };
  }, [open]);

  if (!open || !mounted) return null;

  return createPortal(
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm transition-opacity"
        onClick={() => onOpenChange(false)}
      />
      {/* Sheet Content */}
      {children}
    </>,
    document.body
  );
}

interface SheetContentProps {
  children: React.ReactNode;
  className?: string;
  side?: 'left' | 'right' | 'top' | 'bottom';
}

export function SheetContent({
  children,
  className,
  side = 'right'
}: SheetContentProps) {
  const sideClasses = {
    right: 'inset-y-0 right-0 w-full sm:max-w-2xl animate-in slide-in-from-right',
    left: 'inset-y-0 left-0 w-full sm:max-w-2xl animate-in slide-in-from-left',
    top: 'inset-x-0 top-0 h-full sm:max-h-[80vh] animate-in slide-in-from-top',
    bottom: 'inset-x-0 bottom-0 h-full sm:max-h-[80vh] animate-in slide-in-from-bottom'
  };

  return (
    <div
      className={cn(
        'fixed z-[51] bg-gt-white shadow-lg transition-all duration-300 ease-in-out',
        sideClasses[side],
        className
      )}
    >
      {children}
    </div>
  );
}

interface SheetHeaderProps {
  children: React.ReactNode;
  className?: string;
  onClose?: () => void;
}

export function SheetHeader({
  children,
  className,
  onClose
}: SheetHeaderProps) {
  return (
    <div
      className={cn(
        'flex items-center justify-between border-b px-6 py-4',
        className
      )}
    >
      <div className="flex-1">{children}</div>
      {onClose && (
        <button
          onClick={onClose}
          className="ml-4 rounded-sm opacity-70 ring-offset-background transition-opacity hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
        >
          <X className="h-5 w-5" />
          <span className="sr-only">Close</span>
        </button>
      )}
    </div>
  );
}

interface SheetTitleProps {
  children: React.ReactNode;
  className?: string;
}

export function SheetTitle({ children, className }: SheetTitleProps) {
  return (
    <h2 className={cn('text-lg font-semibold text-gray-900', className)}>
      {children}
    </h2>
  );
}

interface SheetDescriptionProps {
  children: React.ReactNode;
  className?: string;
}

export function SheetDescription({
  children,
  className
}: SheetDescriptionProps) {
  return (
    <p className={cn('text-sm text-gray-600 mt-1', className)}>{children}</p>
  );
}

interface SheetBodyProps {
  children: React.ReactNode;
  className?: string;
}

export function SheetBody({ children, className }: SheetBodyProps) {
  return (
    <div className={cn('flex-1 overflow-y-auto px-6 py-4', className)}>
      {children}
    </div>
  );
}

interface SheetFooterProps {
  children: React.ReactNode;
  className?: string;
}

export function SheetFooter({ children, className }: SheetFooterProps) {
  return (
    <div
      className={cn(
        'flex items-center justify-end gap-2 border-t px-6 py-4',
        className
      )}
    >
      {children}
    </div>
  );
}
