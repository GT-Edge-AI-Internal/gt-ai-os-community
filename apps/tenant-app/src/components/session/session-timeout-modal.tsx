'use client';

import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { AlertTriangle, Clock } from 'lucide-react';

interface SessionTimeoutModalProps {
  open: boolean;
  remainingTime: number; // in seconds (updated externally by IdleTimerProvider)
  onExtendSession: () => void;
  onLogout: () => void;
}

/**
 * Session Timeout Warning Modal (Issue #242)
 *
 * Displays a countdown timer warning users that their session is about to expire.
 * The remainingTime prop is updated externally by IdleTimerProvider using
 * react-idle-timer's getRemainingTime().
 *
 * @see IdleTimerProvider for countdown logic
 */
export function SessionTimeoutModal({
  open,
  remainingTime,
  onExtendSession,
  onLogout,
}: SessionTimeoutModalProps) {
  // Format time as mm:ss
  const formatTime = (seconds: number): string => {
    const minutes = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${minutes}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <Dialog open={open} onOpenChange={() => {/* Prevent closing by clicking outside */}}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-amber-600">
            <AlertTriangle className="w-5 h-5" />
            Session Expiring Soon
          </DialogTitle>
        </DialogHeader>

        <div className="px-6 py-4 space-y-4">
          <DialogDescription>
            Your session will expire due to inactivity. You will be automatically logged out in:
          </DialogDescription>

          <div className="flex items-center justify-center gap-2 py-4">
            <Clock className="w-6 h-6 text-amber-600" />
            <span className="text-3xl font-bold text-amber-600 font-mono">
              {formatTime(remainingTime)}
            </span>
          </div>

          <DialogDescription className="text-center">
            Click "Continue Session" to stay logged in, or "Logout Now" to end your session.
          </DialogDescription>
        </div>

        <DialogFooter>
          <Button
            variant="ghost"
            onClick={onLogout}
            className="text-gray-600"
          >
            Logout Now
          </Button>
          <Button
            variant="primary"
            onClick={onExtendSession}
            className="gap-2"
          >
            <Clock className="w-4 h-4" />
            Continue Session
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
