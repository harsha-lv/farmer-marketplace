/* =====================================================================
   MittiMandi Auth Session & Token Management Module
   Single Source of Truth for Tokens, Automatic 401 Refresh, Mutex Guard
   ===================================================================== */

import { store } from './state.js';
import { API_BASE_URL } from '../config.js';

let refreshPromise = null;
const sessionExpiredCallbacks = [];

export function onSessionExpired(cb) {
  if (typeof cb === 'function') {
    sessionExpiredCallbacks.push(cb);
  }
}

function notifySessionExpired() {
  clearTokens();
  sessionExpiredCallbacks.forEach(cb => {
    try { cb(); } catch (err) { console.error('[AuthSession] Callback error:', err); }
  });
}

export function getAccessToken() {
  const session = store.get('session') || {};
  return session.accessToken || localStorage.getItem('mm_access_token') || null;
}

export function getRefreshToken() {
  const session = store.get('session') || {};
  return session.refreshToken || localStorage.getItem('mm_refresh_token') || null;
}

export function setTokens({ accessToken, refreshToken, tokenType = 'bearer', expiresIn = 900 }) {
  const session = {
    accessToken,
    refreshToken: refreshToken || getRefreshToken(),
    tokenType,
    expiresAt: Date.now() + expiresIn * 1000
  };

  store.set('session', session);

  if (accessToken) {
    localStorage.setItem('mm_access_token', accessToken);
  }
  if (session.refreshToken) {
    localStorage.setItem('mm_refresh_token', session.refreshToken);
  }
}

export function clearTokens() {
  store.set('session', {
    accessToken: null,
    refreshToken: null,
    tokenType: null,
    expiresAt: null
  });
  localStorage.removeItem('mm_access_token');
  localStorage.removeItem('mm_refresh_token');
}

export function isLoggedIn() {
  const token = getAccessToken();
  return Boolean(token && token !== 'expired_invalid_token');
}

/**
 * Mutex-guarded refresh of access token via POST /api/v1/auth/refresh
 */
export async function refreshAuthSession() {
  if (refreshPromise) {
    return refreshPromise;
  }

  const refreshToken = getRefreshToken();
  if (!refreshToken) {
    console.warn('[AuthSession] No refresh token available.');
    return false;
  }

  refreshPromise = (async () => {
    try {
      const csrfToken = getCsrfToken();
      const res = await fetch(`${API_BASE_URL}/auth/refresh`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(csrfToken ? { 'X-CSRF-Token': csrfToken } : {})
        },
        body: JSON.stringify({ refresh_token: refreshToken })
      });

      if (res.ok) {
        const data = await res.json();
        setTokens({
          accessToken: data.access_token,
          refreshToken: data.refresh_token,
          tokenType: data.token_type,
          expiresIn: data.expires_in
        });
        console.log('[AuthSession] Access token refreshed successfully.');
        return true;
      } else {
        console.warn('[AuthSession] Refresh token invalid or expired. Status:', res.status);
        notifySessionExpired();
        return false;
      }
    } catch (err) {
      console.error('[AuthSession] Network error during token refresh:', err);
      return false;
    } finally {
      refreshPromise = null;
    }
  })();

  return refreshPromise;
}

export function getCsrfToken() {
  if (typeof document === 'undefined') return null;
  const match = document.cookie.match(/(?:^|;\s*)(?:csrf_token|XSRF-TOKEN)=([^;]+)/i);
  return match ? decodeURIComponent(match[1]) : null;
}

/**
 * Wrapper around fetch with automatic Authorization header injection and 401 retry
 */
export async function fetchWithAuth(url, options = {}, isRetryAfterRefresh = false) {
  const token = getAccessToken();
  const headers = {
    'Accept': 'application/json',
    ...(options.headers || {})
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const method = (options.method || 'GET').toUpperCase();
  if (method !== 'GET' && method !== 'HEAD') {
    const csrfToken = getCsrfToken();
    if (csrfToken) {
      headers['X-CSRF-Token'] = csrfToken;
    }
  }

  let response;
  try {
    response = await fetch(url, { ...options, headers });
  } catch (netErr) {
    throw netErr;
  }

  if ((response.status === 401 || response.status === 403) && !isRetryAfterRefresh) {
    console.warn('[AuthSession] 401/403 encountered at', url, '— attempting token refresh...');
    const refreshed = await refreshAuthSession();
    if (refreshed) {
      return fetchWithAuth(url, options, true);
    } else {
      notifySessionExpired();
    }
  }

  return response;
}
