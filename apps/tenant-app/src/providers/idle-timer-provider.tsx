'use client';

import { useState, useEffect, useCallback } from 'react';
import { useIdleTimer } from 'react-idle-timer';
import { useAuthStore, useHasHydrated } from '@/stores/auth-store';
import { refreshToken } from '@/services/auth';
import { SessionTimeoutModal } from '@/components/session/session-timeout-modal';
import { SESSION_CONFIG } from '@/config/session';

interface IdleTimerProviderProps {
  children: React.ReactNode;
}

/**
 * GT 2.0 Idle Timer Provider
 *
 * OWASP/NIST Compliant Session Management (Issues #242, #264)
 *
 * This provider implements a hybrid approach:
 * - Server-side session tracking is AUTHORITATIVE (Issue #264)
 * - Client-side IdleTimer provides UX enhancement and backup
 *
 * Server signals processed:
 * - X-Session-Warning: <seconds> - Server says session is about to expire
 * - X-Session-Expired: idle|absolute - Server says session has expired
 *
 * Client-side configuration (secondary to server):
 * - Production: 30 minutes total, warning at 25 minutes (5 min before)
 * - Multi-tab sync: enabled via crossTab
 * - Only active when authenticated
 *
 * Uses react-idle-timer with promptBeforeIdle pattern
 * @see https://idletimer.dev for documentation
 * @see SESSION_CONFIG for timeout values
 */
export function IdleTimerProvider({ children }: IdleTimerProviderProps) {
  const { isAuthenticated, logout, setToken } = useAuthStore();
  const hasHydrated = useHasHydrated(); // Wait for Zustand to hydrate from localStorage
  const [showModal, setShowModal] = useState(false);
  const [remainingTime, setRemainingTime] = useState(0);

  // Debug logging
  useEffect(() => {
    console.log('[IdleTimer] Provider mounted, isAuthenticated:', isAuthenticated, 'hasHydrated:', hasHydrated);
    console.log('[IdleTimer] Config:', {
      timeout: SESSION_CONFIG.TIMEOUT_MS,
      promptBeforeIdle: SESSION_CONFIG.PROMPT_BEFORE_IDLE_MS,
    });
  }, [isAuthenticated, hasHydrated]);

  // Listen for server-side session signals (Issue #264)
  // The server is the authoritative source of truth for session state
  useEffect(() => {
    if (typeof window === 'undefined') return;

    const handleServerWarning = (event: CustomEvent<{ secondsRemaining: number }>) => {
      console.log('[IdleTimer] Server session warning received:', event.detail.secondsRemaining, 'seconds remaining');
      // Show the warning modal if not already showing
      if (!showModal) {
        setShowModal(true);
        setRemainingTime(event.detail.secondsRemaining);
      }
    };

    const handleServerExpired = (event: CustomEvent<{ reason: string }>) => {
      console.log('[IdleTimer] Server session expired:', event.detail.reason);
      setShowModal(false);
      // Map server expiry reason to logout reason
      const logoutReason = event.detail.reason === 'absolute' ? 'session_expired' : 'expired';
      logout(logoutReason);
    };

    window.addEventListener('session-warning', handleServerWarning as EventListener);
    window.addEventListener('session-expired', handleServerExpired as EventListener);

    return () => {
      window.removeEventListener('session-warning', handleServerWarning as EventListener);
      window.removeEventListener('session-expired', handleServerExpired as EventListener);
    };
  }, [showModal, logout]);

  const handleOnPrompt = useCallback(() => {
    console.log('[IdleTimer] Session expiring soon - showing warning modal');
    setShowModal(true);
    // Initial remaining time in seconds
    setRemainingTime(Math.floor(SESSION_CONFIG.PROMPT_BEFORE_IDLE_MS / 1000));
  }, []);

  const handleOnIdle = useCallback(() => {
    console.log('[IdleTimer] Session expired due to inactivity - logging out');
    setShowModal(false);
    logout('expired');
  }, [logout]);

  const handleOnActive = useCallback(() => {
    // Note: onActive only fires when activate() is called while isPrompted
    // Not when user moves mouse during countdown
    console.log('[IdleTimer] Session reactivated');
    setShowModal(false);
  }, []);

  const { activate, getRemainingTime, isPrompted } = useIdleTimer({
    // Total inactivity timeout (see SESSION_CONFIG for values)
    timeout: SESSION_CONFIG.TIMEOUT_MS,
    // Show prompt before timeout (see SESSION_CONFIG for values)
    promptBeforeIdle: SESSION_CONFIG.PROMPT_BEFORE_IDLE_MS,
    // Event handlers
    onPrompt: handleOnPrompt,
    onIdle: handleOnIdle,
    onActive: handleOnActive,
    // Events to track (react-idle-timer defaults + focus)
    events: SESSION_CONFIG.EVENTS as unknown as string[],
    // Throttle event processing for performance
    eventsThrottle: SESSION_CONFIG.EVENTS_THROTTLE_MS,
    // Multi-tab synchronization via BroadcastChannel
    crossTab: true,
    syncTimers: 200,
    // Only run when authenticated AND after Zustand has hydrated from localStorage
    // Fix for Issue #264: Timer was disabled during hydration race condition
    disabled: !hasHydrated || !isAuthenticated,
    // Start automatically when mounted
    startOnMount: true,
  });

  // Update countdown every second when modal is shown
  useEffect(() => {
    let interval: NodeJS.Timeout | null = null;

    if (showModal && isPrompted()) {
      interval = setInterval(() => {
        const remaining = Math.ceil(getRemainingTime() / 1000);
        setRemainingTime(remaining);

        // Safety check - if remaining hits 0, ensure we log out
        if (remaining <= 0) {
          setShowModal(false);
          logout('expired');
        }
      }, 1000);
    }

    return () => {
      if (interval) {
        clearInterval(interval);
      }
    };
  }, [showModal, isPrompted, getRemainingTime, logout]);

  const handleExtendSession = useCallback(async () => {
    console.log('[IdleTimer] User extended session - refreshing token');
    try {
      // Refresh the JWT token (NIST/OWASP compliant - Issue #242)
      const result = await refreshToken();

      if (result.success) {
        console.log('[IdleTimer] Token refreshed successfully');
        // Reset the idle timer and hide modal
        activate();
        setShowModal(false);
      } else if (result.error === 'absolute_timeout') {
        // 8-hour absolute session limit reached (Issue #242)
        // Show different message - user MUST re-login
        console.log('[IdleTimer] Absolute session timeout (8 hours) - forcing re-login');
        logout('session_expired');
      } else {
        console.error('[IdleTimer] Token refresh failed - logging out');
        logout('expired');
      }
    } catch (error) {
      console.error('[IdleTimer] Error refreshing token:', error);
      logout('expired');
    }
  }, [activate, logout]);

  const handleLogoutNow = useCallback(() => {
    console.log('[IdleTimer] User clicked logout from warning modal');
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
