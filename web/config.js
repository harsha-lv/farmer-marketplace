/* =====================================================================
   MittiMandi Web Client Configuration Module
   ===================================================================== */

const isDev = typeof window !== 'undefined' && (
  window.location.origin.includes('localhost') ||
  window.location.origin.includes('127.0.0.1')
);

// In dev (e.g. VS Code Live Server on port 5500), route API calls to the local FastAPI backend.
// In prod (same-origin behind a reverse proxy), route to relative '/api/v1'.
const DEFAULT_DEV_API_BASE = 'http://127.0.0.1:8000/api/v1';
const DEFAULT_PROD_API_BASE = '/api/v1';

export const API_BASE_URL = (() => {
  if (typeof window !== 'undefined') {
    if (window.__AGRI_CONFIG__ && window.__AGRI_CONFIG__.apiBaseUrl) {
      return window.__AGRI_CONFIG__.apiBaseUrl;
    }
    try {
      const stored = localStorage.getItem('agri.apiBase');
      if (stored) return stored;
    } catch (_) {
      // In case localStorage is blocked in sandboxed environments
    }
    return isDev ? DEFAULT_DEV_API_BASE : DEFAULT_PROD_API_BASE;
  }
  return DEFAULT_PROD_API_BASE;
})();

export const API_TIMEOUT_MS = (() => {
  if (typeof window !== 'undefined' && window.__AGRI_CONFIG__?.apiTimeoutMs) {
    return window.__AGRI_CONFIG__.apiTimeoutMs;
  }
  return 15000;
})();

export const SYNC_POLL_INTERVAL_MS = (() => {
  if (typeof window !== 'undefined' && window.__AGRI_CONFIG__?.syncPollIntervalMs) {
    return window.__AGRI_CONFIG__.syncPollIntervalMs;
  }
  return 10000;
})();

export const DEMO_MODE = (() => {
  if (typeof window !== 'undefined') {
    if (window.__AGRI_CONFIG__ && typeof window.__AGRI_CONFIG__.demoMode === 'boolean') {
      return window.__AGRI_CONFIG__.demoMode;
    }
    try {
      const stored = localStorage.getItem('agri.demoMode');
      if (stored !== null) return stored === 'true';
    } catch (_) {}
  }
  // Default to false: real API by default; mock data only allowed when explicitly enabled
  return false;
})();

export function warnDemoFallback(endpointName, reason) {
  console.warn(
    `%c[DEMO_MODE] Using offline mock fallback for '${endpointName}'! Reason: ${reason}. Synthetic data in use.`,
    'background: orange; color: black; font-weight: bold; padding: 2px 6px; border-radius: 3px;'
  );
}

