/**
 * GT 2.0 Session Configuration
 *
 * Server-authoritative session management (Issue #264).
 * The server controls timeout values - these are just for reference/display.
 */

export const SESSION_CONFIG = {
  // How often to poll server for session status (milliseconds)
  POLL_INTERVAL_MS: 60 * 1000, // 60 seconds

  // Server-controlled values (for reference only - server is authoritative)
  // These match the backend SessionService configuration
  SERVER_IDLE_TIMEOUT_HOURS: 4,  // 4 hours - covers meetings, lunch, context-switching
  SERVER_ABSOLUTE_TIMEOUT_HOURS: 8,  // 8 hours - full work day
  SERVER_WARNING_THRESHOLD_MINUTES: 5,
} as const;
