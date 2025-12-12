'use client';

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { AlertTriangle, Clock } from 'lucide-react';

interface SessionTimeoutModalProps {
  open: boolean;
  remainingTime: number; // in seconds
  onAcknowledge: () => void;
}

/**
 * Session Expiration Notice Modal (NIST SP 800-63B AAL2)
 *
 * Informational modal that appears 30 minutes before the 12-hour absolute
 * session timeout. This is NOT for idle timeout (which resets with activity).
 *
 * The absolute timeout cannot be extended - users must re-authenticate after
 * 12 hours regardless of activity. This notice gives users time to save work.
 */
export function SessionTimeoutModal({
  open,
  remainingTime,
  onAcknowledge,
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
            Session Ending Soon
          </DialogTitle>
        </DialogHeader>

        <div className="px-6 py-4 space-y-4">
          <DialogDescription>
            For security, your session will end in:
          </DialogDescription>

          <div className="flex items-center justify-center gap-2 py-4">
            <Clock className="w-6 h-6 text-amber-600" />
            <span className="text-3xl font-bold text-amber-600 font-mono">
              {formatTime(remainingTime)}
            </span>
          </div>

          <DialogDescription className="text-center text-sm">
            Please save any unsaved work. You will need to log in again after your session ends.
            This is a security requirement and cannot be extended.
          </DialogDescription>
        </div>

        <DialogFooter className="justify-center">
          <Button
            variant="default"
            onClick={onAcknowledge}
          >
            I Understand
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
