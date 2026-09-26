/* =====================================================================
   MittiMandi Local Database — IndexedDB Single Source of Truth
   Compliant with WatermelonDB Protocol & SYNC_CONTRACT.md
   ===================================================================== */

const DB_NAME = 'MittiMandiLocalDB';
const DB_VERSION = 2;

// Maximum capped queue for offline outbox writes (never silently drop a write)
export const MAX_OUTBOX_CAP = 1000;

export const SYNC_TABLES = [
  'farmers',
  'land_parcels',
  'lots',
  'assay_reports',
  'buyer_demand',
  'inventory_lots',
  'market_prices',
  'facilities',
  'trade_contracts',
  'consent_artifacts'
];

export const READ_ONLY_TABLES = new Set([
  'market_prices',
  'trade_contracts',
  'consent_artifacts',
  'facilities'
]);

class LocalDatabase {
  constructor() {
    this.db = null;
    this._initPromise = null;
  }

  async init() {
    if (this._initPromise) return this._initPromise;
    this._initPromise = new Promise((resolve, reject) => {
      const request = indexedDB.open(DB_NAME, DB_VERSION);

      request.onupgradeneeded = (event) => {
        const db = event.target.result;
        const oldVersion = event.oldVersion;

        if (oldVersion < 1) {
          // 1. Synchronized Data Tables
          for (const table of SYNC_TABLES) {
            if (!db.objectStoreNames.contains(table)) {
              const store = db.createObjectStore(table, { keyPath: 'id' });
              store.createIndex('updated_at', 'updated_at', { unique: false });
              store.createIndex('_syncStatus', '_syncStatus', { unique: false });
            }
          }

          // 2. Sync Metadata (High-water mark, cursor, schema)
          if (!db.objectStoreNames.contains('sync_meta')) {
            db.createObjectStore('sync_meta', { keyPath: 'key' });
          }

          // 3. Outbox Queue for Unpushed Local Mutations (FIFO with capped limit)
          if (!db.objectStoreNames.contains('sync_outbox')) {
            const outboxStore = db.createObjectStore('sync_outbox', { keyPath: 'queueId', autoIncrement: true });
            outboxStore.createIndex('table', 'table', { unique: false });
            outboxStore.createIndex('record_id', 'record_id', { unique: false });
            outboxStore.createIndex('queued_at', 'queued_at', { unique: false });
          }

          // 4. Conflicts Log (Surfaced to user with resolution details)
          if (!db.objectStoreNames.contains('sync_conflicts')) {
            const conflictStore = db.createObjectStore('sync_conflicts', { keyPath: 'id', autoIncrement: true });
            conflictStore.createIndex('table', 'table', { unique: false });
            conflictStore.createIndex('timestamp', 'timestamp', { unique: false });
          }
        }

        if (oldVersion < 2) {
          /* future migrations */
        }
      };

      request.onsuccess = (event) => {
        this.db = event.target.result;
        resolve(this.db);
      };

      request.onerror = (event) => {
        console.error('IndexedDB open error:', event.target.error);
        reject(event.target.error);
      };
    });

    return this._initPromise;
  }

  // -------------------------------------------------------------------
  // CRUD Operations on Synchronized Tables (Single Source of Truth)
  // -------------------------------------------------------------------

  async get(table, id) {
    await this.init();
    return new Promise((resolve, reject) => {
      const tx = this.db.transaction(table, 'readonly');
      const req = tx.objectStore(table).get(id);
      req.onsuccess = () => resolve(req.result || null);
      req.onerror = () => reject(req.error);
    });
  }

  async getAll(table) {
    await this.init();
    return new Promise((resolve, reject) => {
      const tx = this.db.transaction(table, 'readonly');
      const req = tx.objectStore(table).getAll();
      req.onsuccess = () => {
        // Exclude soft-deleted records from standard active queries
        const active = (req.result || []).filter(r => !r.deleted_at);
        resolve(active);
      };
      req.onerror = () => reject(req.error);
    });
  }

  /**
   * Insert or update record directly in local database and queue mutation in outbox.
   * Enforces queue capping without silently dropping writes.
   */
  async put(table, record, isRemoteSync = false) {
    await this.init();

    // Verify Read-Only enforcement for local mutations
    if (!isRemoteSync && READ_ONLY_TABLES.has(table)) {
      throw new Error(`Table '${table}' is server-authoritative read-only. Local modifications are forbidden.`);
    }

    const now = Date.now();
    const existing = await this.get(table, record.id);
    const action = existing ? 'updated' : 'created';

    const localRecord = {
      ...record,
      created_at: record.created_at || (existing ? existing.created_at : now),
      updated_at: now,
      deleted_at: record.deleted_at || null,
      _syncStatus: isRemoteSync ? 'synced' : action
    };

    return new Promise(async (resolve, reject) => {
      try {
        // Check outbox capacity if this is a local client write
        if (!isRemoteSync) {
          const outboxCount = await this.getOutboxCount();
          if (outboxCount >= MAX_OUTBOX_CAP) {
            // NEVER SILENTLY DROP: Throw explicit error that bubbles up to user
            const error = new Error(`Sync outbox queue limit reached (${MAX_OUTBOX_CAP} operations). Write rejected to prevent data loss. Reconnect to sync.`);
            error.name = 'SyncQueueCapExceededError';
            return reject(error);
          }
        }

        const stores = isRemoteSync ? [table] : [table, 'sync_outbox'];
        const tx = this.db.transaction(stores, 'readwrite');
        const tableStore = tx.objectStore(table);

        tableStore.put(localRecord);

        if (!isRemoteSync) {
          const outboxStore = tx.objectStore('sync_outbox');
          outboxStore.add({
            table,
            record_id: localRecord.id,
            action,
            data: localRecord,
            queued_at: now,
            retry_count: 0
          });
        }

        tx.oncomplete = () => resolve(localRecord);
        tx.onerror = () => reject(tx.error);
      } catch (err) {
        reject(err);
      }
    });
  }

  /**
   * Soft-delete record in local database and queue tombstone in outbox.
   */
  async delete(table, id, isRemoteSync = false) {
    await this.init();

    if (!isRemoteSync && READ_ONLY_TABLES.has(table)) {
      throw new Error(`Table '${table}' is server-authoritative read-only. Local deletions are forbidden.`);
    }

    const existing = await this.get(table, id);
    if (!existing) return null;

    const now = Date.now();
    const tombstoneRecord = {
      ...existing,
      deleted_at: now,
      updated_at: now,
      _syncStatus: isRemoteSync ? 'synced' : 'deleted'
    };

    return new Promise(async (resolve, reject) => {
      try {
        if (!isRemoteSync) {
          const outboxCount = await this.getOutboxCount();
          if (outboxCount >= MAX_OUTBOX_CAP) {
            const error = new Error(`Sync outbox queue limit reached (${MAX_OUTBOX_CAP} operations). Deletion rejected.`);
            error.name = 'SyncQueueCapExceededError';
            return reject(error);
          }
        }

        const stores = isRemoteSync ? [table] : [table, 'sync_outbox'];
        const tx = this.db.transaction(stores, 'readwrite');
        const tableStore = tx.objectStore(table);

        // Keep soft-deleted tombstone locally
        tableStore.put(tombstoneRecord);

        if (!isRemoteSync) {
          const outboxStore = tx.objectStore('sync_outbox');
          outboxStore.add({
            table,
            record_id: id,
            action: 'deleted',
            data: null,
            queued_at: now,
            retry_count: 0
          });
        }

        tx.oncomplete = () => resolve(tombstoneRecord);
        tx.onerror = () => reject(tx.error);
      } catch (err) {
        reject(err);
      }
    });
  }

  // -------------------------------------------------------------------
  // Sync Outbox Queue Management
  // -------------------------------------------------------------------

  async getOutboxCount() {
    await this.init();
    return new Promise((resolve, reject) => {
      const tx = this.db.transaction('sync_outbox', 'readonly');
      const req = tx.objectStore('sync_outbox').count();
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
  }

  async getOutboxItems() {
    await this.init();
    return new Promise((resolve, reject) => {
      const tx = this.db.transaction('sync_outbox', 'readonly');
      const req = tx.objectStore('sync_outbox').getAll();
      req.onsuccess = () => resolve(req.result || []);
      req.onerror = () => reject(req.error);
    });
  }

  async removeOutboxItems(queueIds) {
    if (!queueIds || queueIds.length === 0) return;
    await this.init();
    return new Promise((resolve, reject) => {
      const tx = this.db.transaction('sync_outbox', 'readwrite');
      const store = tx.objectStore('sync_outbox');
      for (const id of queueIds) {
        store.delete(id);
      }
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
  }

  // -------------------------------------------------------------------
  // Sync Metadata & High-Water Mark (lastPulledAt)
  // -------------------------------------------------------------------

  async getMeta(key, defaultValue = null) {
    await this.init();
    return new Promise((resolve, reject) => {
      const tx = this.db.transaction('sync_meta', 'readonly');
      const req = tx.objectStore('sync_meta').get(key);
      req.onsuccess = () => resolve(req.result ? req.result.value : defaultValue);
      req.onerror = () => reject(req.error);
    });
  }

  async setMeta(key, value) {
    await this.init();
    return new Promise((resolve, reject) => {
      const tx = this.db.transaction('sync_meta', 'readwrite');
      tx.objectStore('sync_meta').put({ key, value });
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
  }

  // -------------------------------------------------------------------
  // Conflicts Store (Surfaced to User)
  // -------------------------------------------------------------------

  async recordConflict(conflict) {
    await this.init();
    return new Promise((resolve, reject) => {
      const tx = this.db.transaction('sync_conflicts', 'readwrite');
      tx.objectStore('sync_conflicts').add({
        ...conflict,
        timestamp: Date.now(),
        dismissed: false
      });
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
  }

  async getConflicts() {
    await this.init();
    return new Promise((resolve, reject) => {
      const tx = this.db.transaction('sync_conflicts', 'readonly');
      const req = tx.objectStore('sync_conflicts').getAll();
      req.onsuccess = () => resolve(req.result || []);
      req.onerror = () => reject(req.error);
    });
  }

  async clearConflicts() {
    await this.init();
    return new Promise((resolve, reject) => {
      const tx = this.db.transaction('sync_conflicts', 'readwrite');
      tx.objectStore('sync_conflicts').clear();
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
  }
}

export const localDb = new LocalDatabase();
