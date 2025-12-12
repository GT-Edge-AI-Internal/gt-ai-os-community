'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { useAuthStore } from '@/stores/auth-store';
import { SessionTimeoutModal } from '@/components/session/session-timeout-modal';
import toast from 'react-hot-toast';

interface SessionMonitorProps {
  children: React.ReactNode;
}

// Polling interval: 60 seconds
const POLL_INTERVAL_MS = 60 * 1000;

/**
 * GT 2.0 Control Panel Session Monitor (NIST SP 800-63B AAL2 Compliant)
 *
 * Server-authoritative session management with two timeout types:
 * - Idle timeout (30 min): Resets with activity - polling acts as heartbeat
 * - Absolute timeout (12 hr): Cannot be extended - forces re-authentication
 *
 * How it works:
 * 1. Polls /api/v1/session/status every 60 seconds
 * 2. Polling resets idle timeout, so active users won't hit idle limit
 * 3. When absolute timeout < 30 min remaining, show informational notice
 * 4. User acknowledges notice (can't extend absolute timeout)
 * 5. If is_valid=false, force logout
 */
export function SessionMonitor({ children }: SessionMonitorProps) {
  const { isAuthenticated, logout, token } = useAuthStore();
  const [showModal, setShowModal] = useState(false);
  const [remainingTime, setRemainingTime] = useState(0);
  const [hasHydrated, setHasHydrated] = useState(false);
  const [hasAcknowledged, setHasAcknowledged] = useState(false);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);
  const countdownRef = useRef<NodeJS.Timeout | null>(null);

  // Wait for Zustand to hydrate from localStorage
  useEffect(() => {
    setHasHydrated(true);
  }, []);

  // Check session status from server
  const checkSessionStatus = useCallback(async () => {
    if (!isAuthenticated || !token) return;

    try {
      const response = await fetch('/api/v1/session/status', {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (response.status === 401 || response.status === 503) {
        // Session expired or service unavailable - logout
        console.log('[SessionMonitor] Session invalid, logging out');
        toast.error('Your session has expired. Please log in again.');
        logout();
        window.location.href = '/auth/login';
        return;
      }

      if (!response.ok) {
        console.warn('[SessionMonitor] Session check failed:', response.status);
        return;
      }

      const data = await response.json();

      if (!data.is_valid) {
        // Session expired
        console.log('[SessionMonitor] Server says session invalid');
        toast.error('Your session has expired. Please log in again.');
        logout();
        window.location.href = '/auth/login';
        return;
      }

      // Update remaining time (use absolute timeout for display)
      if (data.absolute_seconds_remaining !== null) {
        setRemainingTime(data.absolute_seconds_remaining);
      }

      // Show warning if needed (and user hasn't already acknowledged)
      if (data.show_warning && !showModal && !hasAcknowledged) {
        console.log('[SessionMonitor] Absolute timeout approaching, showing notice');
        setShowModal(true);
      }

    } catch (error) {
      console.error('[SessionMonitor] Error checking session:', error);
      // On network error, don't logout immediately - wait for next poll
    }
  }, [isAuthenticated, token, showModal, hasAcknowledged, logout]);

  // Start/stop polling based on auth state
  useEffect(() => {
    if (!hasHydrated || !isAuthenticated) {
      // Clear any existing interval and reset state
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
      setHasAcknowledged(false); // Reset on logout
      return;
    }

    // Initial check
    checkSessionStatus();

    // Start polling
    intervalRef.current = setInterval(checkSessionStatus, POLL_INTERVAL_MS);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [hasHydrated, isAuthenticated, checkSessionStatus]);

  // Countdown timer when modal is shown
  useEffect(() => {
    if (showModal && remainingTime > 0) {
      countdownRef.current = setInterval(() => {
        setRemainingTime(prev => {
          const newTime = prev - 1;
          if (newTime <= 0) {
            // Time's up - logout
            setShowModal(false);
            toast.error('Your session has expired. Please log in again.');
            logout();
            window.location.href = '/auth/login';
            return 0;
          }
          return newTime;
        });
      }, 1000);
    }

    return () => {
      if (countdownRef.current) {
        clearInterval(countdownRef.current);
        countdownRef.current = null;
      }
    };
  }, [showModal, logout]);

  // Handle "I Understand" button - just dismiss the notice
  const handleAcknowledge = useCallback(() => {
    console.log('[SessionMonitor] User acknowledged session expiration notice');
    setShowModal(false);
    setHasAcknowledged(true);
  }, []);

  return (
    <>
      {children}
      <SessionTimeoutModal
        open={showModal}
        remainingTime={remainingTime}
        onAcknowledge={handleAcknowledge}
      />
    </>
  );
}
