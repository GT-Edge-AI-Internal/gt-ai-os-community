/**
 * GT 2.0 Session Configuration
 *
 * NIST SP 800-63B AAL2 Compliant Session Management (Issue #264).
 * The server controls timeout values - these are just for reference/display.
 */

export const SESSION_CONFIG = {
  // How often to poll server for session status (milliseconds)
  POLL_INTERVAL_MS: 60 * 1000, // 60 seconds

  // Server-controlled values (for reference only - server is authoritative)
  // These match the backend SessionService configuration (NIST AAL2 compliant)
  SERVER_IDLE_TIMEOUT_MINUTES: 30,  // 30 minutes - NIST AAL2 requirement
  SERVER_ABSOLUTE_TIMEOUT_HOURS: 12,  // 12 hours - NIST AAL2 maximum
  SERVER_WARNING_THRESHOLD_MINUTES: 5,
} as const;
