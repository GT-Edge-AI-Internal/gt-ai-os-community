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
 * GT 2.0 Control Panel Session Monitor
 *
 * Simplified server-authoritative session management.
 * Replaces complex react-idle-timer with simple server polling.
 *
 * How it works:
 * 1. Polls /api/v1/session/status every 60 seconds
 * 2. Server returns seconds_remaining and show_warning
 * 3. When show_warning=true (< 5 min remaining), display modal
 * 4. User can extend session or logout
 * 5. If is_valid=false, force logout
 *
 * Session timeouts (server-controlled):
 * - Idle: 4 hours (covers meetings, lunch, context-switching)
 * - Absolute: 8 hours (full work day)
 * - Warning: 5 minutes before expiry
 */
export function SessionMonitor({ children }: SessionMonitorProps) {
  const { isAuthenticated, logout, token } = useAuthStore();
  const [showModal, setShowModal] = useState(false);
  const [remainingTime, setRemainingTime] = useState(0);
  const [hasHydrated, setHasHydrated] = useState(false);
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

      // Update remaining time
      setRemainingTime(data.seconds_remaining);

      // Show warning if needed
      if (data.show_warning && !showModal) {
        console.log('[SessionMonitor] Session expiring soon, showing warning');
        setShowModal(true);
      }

    } catch (error) {
      console.error('[SessionMonitor] Error checking session:', error);
      // On network error, don't logout immediately - wait for next poll
    }
  }, [isAuthenticated, token, showModal, logout]);

  // Start/stop polling based on auth state
  useEffect(() => {
    if (!hasHydrated || !isAuthenticated) {
      // Clear any existing interval
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
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
            toast.error('Your session has expired due to inactivity.');
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

  // Handle "Continue Session" button
  const handleExtendSession = useCallback(() => {
    console.log('[SessionMonitor] User extending session');
    // Simply close the modal - the next poll will reset the idle timer
    // by making an authenticated request to the server
    setShowModal(false);
    toast.success('Session extended');
    // Immediately check status to get new remaining time
    checkSessionStatus();
  }, [checkSessionStatus]);

  // Handle "Logout Now" button
  const handleLogoutNow = useCallback(() => {
    console.log('[SessionMonitor] User clicked logout');
    setShowModal(false);
    logout();
    window.location.href = '/auth/login';
  }, [logout]);

  return (
    <>
      {children}
      <SessionTimeoutModal
        open={showModal}
        remainingTime={remainingTime}
        onExtendSession={handleExtendSession}
        onLogout={handleLogoutNow}
      />
    </>
  );
}
