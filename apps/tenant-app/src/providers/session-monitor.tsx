'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { useAuthStore, useHasHydrated } from '@/stores/auth-store';
import { refreshToken, getAuthToken } from '@/services/auth';
import { SessionTimeoutModal } from '@/components/session/session-timeout-modal';

interface SessionMonitorProps {
  children: React.ReactNode;
}

// Polling interval: 60 seconds
const POLL_INTERVAL_MS = 60 * 1000;

// Warning threshold: show warning when < 5 minutes remaining
const WARNING_THRESHOLD_SECONDS = 5 * 60;

/**
 * GT 2.0 Session Monitor
 *
 * Simplified server-authoritative session management.
 * Replaces complex react-idle-timer with simple server polling.
 *
 * How it works:
 * 1. Polls /api/v1/auth/session/status every 60 seconds
 * 2. Server returns seconds_remaining and show_warning
 * 3. When show_warning=true (< 5 min remaining), display modal
 * 4. User can extend session (calls refresh endpoint) or logout
 * 5. If is_valid=false, force logout
 *
 * Benefits over react-idle-timer:
 * - Server is single source of truth
 * - No client-side activity tracking needed
 * - Polling acts as heartbeat, keeping session alive
 * - Much simpler code (~60 lines vs ~200 lines)
 */
export function SessionMonitor({ children }: SessionMonitorProps) {
  const { isAuthenticated, logout } = useAuthStore();
  const hasHydrated = useHasHydrated();
  const [showModal, setShowModal] = useState(false);
  const [remainingTime, setRemainingTime] = useState(0);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);
  const countdownRef = useRef<NodeJS.Timeout | null>(null);

  // Check session status from server
  const checkSessionStatus = useCallback(async () => {
    // Get fresh token from store (not stale closure value) to avoid race condition
    // after token refresh where old token would cause 401
    const currentToken = getAuthToken();
    if (!isAuthenticated || !currentToken) return;

    try {
      const response = await fetch('/api/v1/auth/session/status', {
        headers: {
          'Authorization': `Bearer ${currentToken}`,
          'Content-Type': 'application/json',
        },
      });

      if (response.status === 401 || response.status === 503) {
        // Session expired or service unavailable - logout
        console.log('[SessionMonitor] Session invalid, logging out');
        logout('expired');
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
        logout('expired');
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
  }, [isAuthenticated, showModal, logout]);  // Note: token removed - we fetch fresh via getAuthToken()

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
            logout('expired');
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
  const handleExtendSession = useCallback(async () => {
    console.log('[SessionMonitor] User extending session');
    try {
      const result = await refreshToken();

      if (result.success) {
        console.log('[SessionMonitor] Session extended successfully');
        setShowModal(false);
        // Immediately check status to get new remaining time
        checkSessionStatus();
      } else if (result.error === 'absolute_timeout') {
        // 8-hour absolute limit reached
        console.log('[SessionMonitor] Absolute timeout - must re-login');
        logout('session_expired');
      } else {
        console.error('[SessionMonitor] Token refresh failed');
        logout('expired');
      }
    } catch (error) {
      console.error('[SessionMonitor] Error extending session:', error);
      logout('expired');
    }
  }, [checkSessionStatus, logout]);

  // Handle "Logout Now" button
  const handleLogoutNow = useCallback(() => {
    console.log('[SessionMonitor] User clicked logout');
    setShowModal(false);
    logout('manual');
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
