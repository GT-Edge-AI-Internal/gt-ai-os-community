/**
 * GT 2.0 Control Panel Session Configuration (NIST SP 800-63B AAL2 Compliant)
 *
 * Server-authoritative session management (Issue #264).
 * The server controls timeout values - these are just for reference/display.
 *
 * NIST AAL2 Requirements:
 * - Idle timeout: 30 minutes (SHALL requirement for inactivity)
 * - Absolute timeout: 12 hours (SHALL maximum session duration)
 *
 * Note: Since polling acts as a heartbeat (resets idle timer), idle timeout
 * only triggers when browser is closed. Warning modal is for absolute timeout only.
 */

export const SESSION_CONFIG = {
  // How often to poll server for session status (milliseconds)
  POLL_INTERVAL_MS: 60 * 1000, // 60 seconds

  // Server-controlled values (for reference only - server is authoritative)
  // These match the backend SessionService configuration
  SERVER_IDLE_TIMEOUT_MINUTES: 30,  // 30 minutes - NIST AAL2 requirement
  SERVER_ABSOLUTE_TIMEOUT_HOURS: 12,  // 12 hours - NIST AAL2 maximum
  SERVER_WARNING_THRESHOLD_MINUTES: 30,  // Show notice 30 min before absolute timeout
} as const;
