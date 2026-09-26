/* =====================================================================
   MittiMandi Offline-First Sync Engine
   Wire Protocol: SYNC_CONTRACT.md (/api/v1/sync)
   Semantics: Pull-first, then push, exponential backoff, 401 refresh,
   and deterministic conflict resolution for all contract types.
   ===================================================================== */

import { localDb, SYNC_TABLES, READ_ONLY_TABLES } from './db.js';
import { store } from './state.js';
import { API_BASE_URL, API_TIMEOUT_MS, SYNC_POLL_INTERVAL_MS } from '../config.js';
import { renderPersistentIndicator } from './components/toast.js';
import { fetchWithAuth as sessionFetchWithAuth, refreshAuthSession as sessionRefreshAuthSession } from './auth-session.js';

export class SyncHttpError extends Error {
  constructor(status, statusText, url, bodyText, retryAfter = null) {
    super(`HTTP ${status} (${statusText || 'Error'}) on ${url}`);
    this.name = 'SyncHttpError';
    this.status = status;
    this.statusText = statusText;
    this.url = url;
    this.bodyText = bodyText;
    this.retryAfter = retryAfter;
    this.authExpired = false;
  }
}

// Backoff configuration
const INITIAL_BACKOFF_MS = 1000;
const MAX_BACKOFF_MS = 60000;
const DEFAULT_MAX_RETRIES = 10;

class SyncEngine {
  constructor() {
    this.isSyncing = false;
    this.retryCount = 0;
    this.maxRetries = DEFAULT_MAX_RETRIES;
    this.isParked = false;
    this.retryTimeoutId = null;
    this.pendingSyncOnFinish = false;
    this.hasLogged404ConfigError = false;

    // Bind browser connectivity events
    if (typeof window !== 'undefined') {
      window.addEventListener('online', () => this.onConnectivityRegained());
      window.addEventListener('offline', () => this.onConnectivityLost());
    }
  }

  clearRetryTimer() {
    if (this.retryTimeoutId) {
      clearTimeout(this.retryTimeoutId);
      this.retryTimeoutId = null;
    }
  }

  renderPersistentIndicator(show, text = '') {
    renderPersistentIndicator(show, text);
  }

  // -------------------------------------------------------------------
  // Connectivity & Event Listeners
  // -------------------------------------------------------------------

  onConnectivityRegained() {
    console.log('[SyncEngine] Connectivity regained. Scheduling pull-first sync...');
    store.set('isOnline', true);
    this.retryCount = 0;
    this.isParked = false;
    this.hasLogged404ConfigError = false;
    this.clearRetryTimer();
    this.renderPersistentIndicator(false);
    this.updateStatus('online');
    // On connectivity regain: pull first, then push
    this.triggerSync().catch(() => {});
  }

  onConnectivityLost() {
    console.log('[SyncEngine] Connectivity lost. Switched to offline field mode.');
    store.set('isOnline', false);
    this.updateStatus('offline', 'Device is offline. Changes buffered in local SQLite/IndexedDB outbox.');
    this.clearRetryTimer();
    this.renderPersistentIndicator(false);
  }

  updateStatus(status, detail = null) {
    store.update('syncState', s => ({
      ...s,
      status,
      detail: detail || s.detail,
      lastUpdated: Date.now()
    }));
  }

  // -------------------------------------------------------------------
  // Authenticated Request with Automatic 401 Token Refresh
  // -------------------------------------------------------------------

  async fetchWithAuth(url, options = {}, isRetryAfterRefresh = false) {
    const response = await sessionFetchWithAuth(url, options, isRetryAfterRefresh);
    if ((response.status === 401 || response.status === 403)) {
      const err = new SyncHttpError(response.status, 'Session Expired', url, 'AUTH_EXPIRED: Session refresh failed. Please log in again to sync.');
      err.authExpired = true;
      throw err;
    }
    return response;
  }

  async refreshAuthSession() {
    return sessionRefreshAuthSession();
  }

  // -------------------------------------------------------------------
  // Main Synchronization Routine: Pull First, Then Push
  // -------------------------------------------------------------------

  async triggerSync() {
    try {
      if (this.isSyncing) {
        this.pendingSyncOnFinish = true;
        return;
      }

      const isOnline = store.get('isOnline');
      if (!isOnline || !navigator.onLine) {
        this.updateStatus('offline', 'Device is offline. Changes buffered in local SQLite/IndexedDB outbox.');
        return;
      }

      // Manual or event trigger unparks if parked
      if (this.isParked) {
        this.isParked = false;
        this.retryCount = 0;
        this.clearRetryTimer();
        this.renderPersistentIndicator(false);
      }

      this.isSyncing = true;
      this.updateStatus('syncing', 'Starting pull-first sync...');

      try {
        // ===============================================================
        // PHASE 1: PULL REMOTE CHANGES (Delta Sync)
        // ===============================================================
        this.updateStatus('pulling', 'Pulling remote updates since last watermark...');
        const pullResult = await this.executePullPhase();

        // ===============================================================
        // PHASE 2: PUSH LOCAL MUTATIONS (Outbox Flush)
        // ===============================================================
        this.updateStatus('pushing', 'Pushing local outbox changes to server...');
        const pushResult = await this.executePushPhase(pullResult.lastPulledAt);

        // Successfully synced!
        this.retryCount = 0;
        this.isParked = false;
        this.hasLogged404ConfigError = false;
        this.clearRetryTimer();
        this.renderPersistentIndicator(false);

        const outboxCount = await localDb.getOutboxCount();
        const conflicts = await localDb.getConflicts();
        store.set('pendingSyncCount', outboxCount);
        store.set('conflicts', conflicts);

        this.updateStatus('idle', `Sync complete! Last watermark: ${new Date(pullResult.lastPulledAt).toLocaleTimeString()}`);
        if (window.showToast) {
          if (pushResult.conflictsCount > 0) {
            window.showToast(`Sync complete with ${pushResult.conflictsCount} conflict(s) resolved.`);
          } else if (pushResult.pushedCount > 0) {
            window.showToast(`Synced ${pushResult.pushedCount} changes to server.`);
          }
        }
      } catch (error) {
        this.handleSyncFailure(error);
      } finally {
        this.isSyncing = false;
        if (this.pendingSyncOnFinish && !this.isParked && (store.get('isOnline') && navigator.onLine)) {
          this.pendingSyncOnFinish = false;
          setTimeout(() => this.triggerSync().catch(() => {}), 100);
        }
      }
    } catch (unhandled) {
      console.warn('[SyncEngine] Caught unexpected error in triggerSync wrapper:', unhandled);
    }
  }

  // -------------------------------------------------------------------
  // Phase 1: Pull Implementation with Continuation Cursor Pagination
  // -------------------------------------------------------------------

  async executePullPhase() {
    let lastPulledAt = await localDb.getMeta('lastPulledAt', null);
    let hasMore = true;
    let cursor = null;
    let totalPulled = 0;
    let newWatermark = null;

    // Cursor pagination loop
    while (hasMore) {
      const params = new URLSearchParams();
      if (lastPulledAt) params.append('lastPulledAt', String(lastPulledAt));
      params.append('limit', '500');
      params.append('schemaVersion', '1');
      params.append('migrationVersion', '1');
      if (cursor) params.append('cursor', cursor);

      const url = `${API_BASE_URL}/sync/pull?${params.toString()}`;
      const response = await this.fetchWithAuth(url);

      if (!response.ok) {
        const bodyText = await response.text();
        const retryAfter = response.headers.get('Retry-After');
        throw new SyncHttpError(response.status, response.statusText, url, bodyText, retryAfter);
      }

      const data = await response.json();

      // Note on contract discrepancy:
      // SYNC_CONTRACT.md specifies "timestamp", while backend schema SyncPullResponse returns "newLastPulledAt".
      // We support both defensively:
      newWatermark = data.newLastPulledAt || data.timestamp || Date.now();

      // Apply pulled changes locally into IndexedDB
      if (data.changes) {
        for (const [table, changes] of Object.entries(data.changes)) {
          // 1. Process Deleted Tombstones
          if (Array.isArray(changes.deleted)) {
            for (const id of changes.deleted) {
              await localDb.delete(table, id, true); // isRemoteSync = true
              totalPulled++;
            }
          }

          // 2. Process Created & Updated Records
          const recordsToUpsert = [...(changes.created || []), ...(changes.updated || [])];
          for (const record of recordsToUpsert) {
            // Apply into local single source of truth
            await localDb.put(table, record, true); // isRemoteSync = true
            totalPulled++;
          }
        }
      }

      hasMore = Boolean(data.hasMore || data.has_more);
      cursor = data.cursor || data.next_cursor || null;

      if (hasMore && !cursor) {
        // Prevent infinite loop if server flags hasMore without cursor
        break;
      }
    }

    // Commit new watermark to sync_meta only after all pages are applied
    if (newWatermark) {
      await localDb.setMeta('lastPulledAt', newWatermark);
      lastPulledAt = newWatermark;
    }

    return { lastPulledAt, totalPulled };
  }

  // -------------------------------------------------------------------
  // Phase 2: Push Implementation & Conflict Handling
  // -------------------------------------------------------------------

  async executePushPhase(lastPulledAt) {
    const outboxItems = await localDb.getOutboxItems();
    if (!outboxItems || outboxItems.length === 0) {
      return { pushedCount: 0, conflictsCount: 0 };
    }

    // Format changes matching SYNC_CONTRACT.md Section 4
    const changesPayload = {};
    const processedQueueIds = [];

    for (const item of outboxItems) {
      processedQueueIds.push(item.queueId);
      if (!changesPayload[item.table]) {
        changesPayload[item.table] = { created: [], updated: [], deleted: [] };
      }

      if (item.action === 'created') {
        changesPayload[item.table].created.push(item.data);
      } else if (item.action === 'updated') {
        changesPayload[item.table].updated.push(item.data);
      } else if (item.action === 'deleted') {
        changesPayload[item.table].deleted.push(item.record_id);
      }
    }

    const payload = {
      changes: changesPayload,
      lastPulledAt: lastPulledAt || 0,
      schemaVersion: 1,
      migrationVersion: 1
    };

    const pushUrl = `${API_BASE_URL}/sync/push`;
    const response = await this.fetchWithAuth(pushUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      const bodyText = await response.text();
      const retryAfter = response.headers.get('Retry-After');
      throw new SyncHttpError(response.status, response.statusText, pushUrl, bodyText, retryAfter);
    }

    const pushResponse = await response.json();
    let conflictsCount = 0;

    // Handle Conflicts Array from Server
    if (Array.isArray(pushResponse.conflicts) && pushResponse.conflicts.length > 0) {
      conflictsCount = pushResponse.conflicts.length;
      for (const conflict of pushResponse.conflicts) {
        await this.handleServerConflict(conflict);
      }
    }

    // Clear successfully committed mutations from outbox
    await localDb.removeOutboxItems(processedQueueIds);

    return {
      pushedCount: processedQueueIds.length,
      conflictsCount
    };
  }

  // -------------------------------------------------------------------
  // Comprehensive Conflict Resolution Handler (Contract Defined)
  // -------------------------------------------------------------------

  async handleServerConflict(conflict) {
    console.warn(`[SyncEngine] Conflict detected on table '${conflict.table}' id '${conflict.id}':`, conflict);

    const { table, id, type, resolution, server_version, client_version, message } = conflict;

    // 1. created_existing_uuid -> merged_as_update
    // The server already had a record with this UUID and merged the client's attributes as an update.
    if (resolution === 'merged_as_update' || type === 'created_existing_uuid') {
      if (server_version) {
        await localDb.put(table, server_version, true);
      }
      await localDb.recordConflict({
        table,
        id,
        type: type || 'created_existing_uuid',
        resolution: 'merged_as_update',
        title: 'Merged with Existing Server Record',
        message: message || `Record ${id} already existed on server. Merged attributes as update.`,
        server_version
      });
    }

    // 2. concurrent_update -> server_won (Last-Writer-Wins)
    // Server has a newer updated_at timestamp. The server version overrides local changes.
    else if (resolution === 'server_won' || (type === 'concurrent_update' && resolution !== 'client_won')) {
      if (server_version) {
        await localDb.put(table, server_version, true);
      }
      await localDb.recordConflict({
        table,
        id,
        type: 'concurrent_update',
        resolution: 'server_won (Last-Writer-Wins)',
        title: 'Server Timestamp Precedence (LWW)',
        message: message || `Concurrent edit detected. Server record was newer and has been retained.`,
        server_version,
        client_version
      });
    }

    // 3. concurrent_update -> client_won
    // Client had newer updated_at timestamp; client mutation was accepted.
    else if (resolution === 'client_won') {
      await localDb.recordConflict({
        table,
        id,
        type: 'concurrent_update',
        resolution: 'client_won',
        title: 'Client Edit Accepted (LWW)',
        message: `Local update for ${table} (${id}) prevailed under Last-Writer-Wins.`,
        client_version
      });
    }

    // 4. read_only_table -> server_authoritative
    // Client attempted to mutate a read-only table (market_prices, trade_contracts, consent_artifacts, facilities).
    // Local mutation is reverted to server-authoritative state.
    else if (resolution === 'server_authoritative' || type === 'read_only_table') {
      if (server_version) {
        await localDb.put(table, server_version, true);
      } else {
        await localDb.delete(table, id, true);
      }
      await localDb.recordConflict({
        table,
        id,
        type: 'read_only_table',
        resolution: 'server_authoritative',
        title: 'Read-Only Table Violation',
        message: message || `Table '${table}' is server-authoritative. Local changes were reverted.`,
        server_version
      });
    }

    // 5. delete_rejected -> rejected_active_lien_or_listing
    // Deletion rejected because of an active pledge lien or registered ONDC listing.
    // Restore the record locally.
    else if (resolution === 'rejected_active_lien_or_listing' || type === 'delete_rejected') {
      if (server_version) {
        await localDb.put(table, server_version, true);
      }
      await localDb.recordConflict({
        table,
        id,
        type: 'delete_rejected',
        resolution: 'rejected_active_lien_or_listing',
        title: 'Deletion Rejected: Active Lien / Listing',
        message: message || `Cannot delete ${table} record ${id}: active pledge lien or ONDC listing exists.`,
        server_version
      });
    }

    // 6. Generic Fallback
    else {
      if (server_version) {
        await localDb.put(table, server_version, true);
      }
      await localDb.recordConflict({
        table,
        id,
        type: type || 'conflict',
        resolution: resolution || 'server_resolved',
        title: 'Sync Conflict Resolved',
        message: message || 'Conflict resolved by server.',
        server_version
      });
    }
  }

  // -------------------------------------------------------------------
  // Exponential Backoff Retry Engine
  // -------------------------------------------------------------------

  handleSyncFailure(error) {
    const isOnline = store.get('isOnline');

    if (!isOnline || !navigator.onLine) {
      this.updateStatus('offline', 'Device went offline. Retries paused.');
      this.clearRetryTimer();
      this.renderPersistentIndicator(false);
      return;
    }

    const is404 = Boolean(error && error.status === 404);
    const isAuthExpired = Boolean(error && (error.authExpired || error.status === 401 || error.status === 403));
    const is429 = Boolean(error && error.status === 429);
    const is5xx = Boolean(error && error.status >= 500 && error.status < 600);
    const isNetworkError = !error || !error.status || error instanceof TypeError;

    // Logging requirement:
    // First failure logged in full; every subsequent failure logged as a single one-line summary with the attempt number.
    // Never re-print the same HTML error body.
    if (this.retryCount === 0) {
      console.error('[SyncEngine] Synchronization cycle failed:', error);
    } else {
      const summaryMsg = error && error.status
        ? `HTTP ${error.status} on ${error.url || API_BASE_URL}`
        : (error && error.message ? error.message : 'Network connection failure');
      console.warn(`[SyncEngine] Retry #${this.retryCount} failed: ${summaryMsg}`);
    }

    // Class A: HTTP 404 -> CONFIG error
    if (is404) {
      if (!this.hasLogged404ConfigError) {
        this.hasLogged404ConfigError = true;
        console.error(`[SyncEngine] CONFIG ERROR: 404 Not Found at ${error.url || API_BASE_URL}. The configured API base URL is incorrect. Sync stopped.`);
      }
      this.updateStatus('error', `Config error: 404 Not Found at ${error.url || API_BASE_URL}. Sync halted.`);
      this.clearRetryTimer();
      return; // STOP retrying permanently (404 will never heal itself)
    }

    // Class B: HTTP 401/403 -> Session expired
    if (isAuthExpired) {
      this.updateStatus('auth_expired', 'Session expired — sign in again to sync.');
      if (window.showToast) {
        window.showToast('Session expired — sign in again.');
      }
      this.clearRetryTimer();
      return; // STOP retrying
    }

    // Class C: Network / 5xx / 429 -> Retry with backoff
    this.retryCount++;

    // Max consecutive failures check (default 10)
    if (this.retryCount >= this.maxRetries) {
      this.isParked = true;
      this.updateStatus('unreachable', `Backend unreachable after ${this.retryCount} attempts. Sync parked. Click "Retry now" or reconnect to resume.`);
      this.renderPersistentIndicator(true, `Backend unreachable — parked after ${this.retryCount} failed attempts.`);
      this.clearRetryTimer();
      return;
    }

    // Calculate delay:
    let delayMs;
    if (is429 && error.retryAfter) {
      const parsedSeconds = parseInt(error.retryAfter, 10);
      if (!isNaN(parsedSeconds) && parsedSeconds > 0) {
        delayMs = parsedSeconds * 1000;
      } else {
        const retryDate = new Date(error.retryAfter).getTime();
        delayMs = !isNaN(retryDate) && retryDate > Date.now() ? retryDate - Date.now() : 5000;
      }
    } else {
      // Exponential backoff + jitter: 1s -> 2s -> 4s -> 8s -> ... capped at 60s
      const jitter = Math.floor(Math.random() * 500);
      delayMs = Math.min(INITIAL_BACKOFF_MS * Math.pow(2, this.retryCount - 1), MAX_BACKOFF_MS) + jitter;
    }

    const seconds = Math.round(delayMs / 1000);
    const detailMsg = isNetworkError
      ? `Backend unreachable (connection failed). Retrying in ${seconds}s (attempt #${this.retryCount}/${this.maxRetries})...`
      : `Sync failed (HTTP ${error.status || 'ERR'}). Retrying in ${seconds}s (attempt #${this.retryCount}/${this.maxRetries})...`;

    this.updateStatus('retrying', detailMsg);
    this.renderPersistentIndicator(true, `Backend unreachable — retrying in ${seconds}s (attempt #${this.retryCount}/${this.maxRetries})`);

    this.clearRetryTimer();
    this.retryTimeoutId = setTimeout(() => {
      this.retryTimeoutId = null;
      this.triggerSync().catch(() => {});
    }, delayMs);
  }
}

export const syncEngine = new SyncEngine();
