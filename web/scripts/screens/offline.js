/* =====================================================================
   MittiMandi Screen: Offline-First Synchronization & Conflict Hub
   Wire Protocol: SYNC_CONTRACT.md (/api/v1/sync)
   Migrated onto shared component library (F1 Foundation)
   ===================================================================== */

import { localDb, MAX_OUTBOX_CAP } from '../db.js';
import { store } from '../state.js';
import { syncEngine } from '../sync.js';
import { renderBadge } from '../components/badge.js';
import { renderButton } from '../components/button.js';
import { renderCard } from '../components/card.js';

export function renderOffline() {
  const isOnline = store.get('isOnline');
  const syncState = store.get('syncState') || {};
  const conflicts = store.get('conflicts') || [];
  const pendingCount = store.get('pendingSyncCount') || 0;
  const session = store.get('session') || {};

  return `
    <div class="screen-content">
      <!-- Title & Protocol Badge -->
      <div>
        <div class="flex-row justify-between items-center">
          ${renderBadge('WATERMELONDB DELTA SYNC', 'primary')}
          ${isOnline ? renderBadge('ONLINE', 'success') : renderBadge('AIRPLANE MODE (OFFLINE)', 'danger')}
        </div>
        <h2 class="headline-md mt-xs">Sync & Local Database Hub</h2>
        <p class="caption text-secondary">
          Contract: <code>SYNC_CONTRACT.md</code> · Local IndexedDB as Single Source of Truth
        </p>
      </div>

      <!-- Network State & Airplane Mode Simulator -->
      ${renderCard({
        content: `
          <div class="flex-row justify-between items-center">
            <div>
              <span class="caption text-muted">Edge Network Connection</span>
              <div class="flex-row items-center gap-sm mt-xs">
                <div class="connection-indicator-dot ${isOnline ? 'online' : 'offline'}"></div>
                <strong class="body-md">${isOnline ? 'Connected (5G / Rural WiFi)' : 'Simulated Airplane Mode (Field Edge)'}</strong>
              </div>
            </div>

            ${renderButton({
              text: isOnline ? '✈️ Go Airplane Mode' : '📶 Reconnect Online',
              variant: isOnline ? 'secondary' : 'primary',
              size: 'sm',
              action: 'toggle-airplane'
            })}
          </div>
        `
      })}

      <!-- Sync Status & High-Water Mark Banner -->
      ${renderCard({
        variant: 'primary-gradient',
        content: `
          <div class="flex-row justify-between items-center">
            <div>
              <span class="label-md text-accent">Sync Engine Pipeline</span>
              <div class="caption text-primary mt-2xs">
                ${syncState.detail || 'Ready to synchronize'}
              </div>
            </div>
            ${renderBadge((syncState.status || 'idle').toUpperCase(), syncState.status === 'syncing' || syncState.status === 'pulling' || syncState.status === 'pushing' ? 'warning' : 'primary')}
          </div>

          <div class="flex-row justify-between items-center mt-sm pt-xs border-t caption">
            <span class="text-muted">High-Water Mark (lastPulledAt):</span>
            <span class="data-xs text-success" id="display-last-pulled-at">Loading...</span>
          </div>

          <div class="mt-sm">
            ${renderButton({
              text: 'Pull First, Then Push (/api/v1/sync) 🔄',
              variant: 'primary',
              size: 'md',
              isBlock: true,
              disabled: !isOnline,
              action: 'manual-sync'
            })}
          </div>
        `
      })}

      <!-- Capped Outbox Queue (Never Silently Drop a Write) -->
      ${renderCard({
        content: `
          <div class="flex-row justify-between items-center mb-xs">
            <span class="label-md">Local Mutation Outbox</span>
            ${renderBadge(`${pendingCount} / ${MAX_OUTBOX_CAP} Max Capped`, pendingCount > 0 ? 'warning' : 'success')}
          </div>

          <progress class="outbox-progress-track ${pendingCount > 800 ? 'warning' : ''}" value="${pendingCount}" max="${MAX_OUTBOX_CAP}"></progress>

          <div id="outbox-items-container" class="outbox-list">
            <div class="caption text-muted text-center pt-sm">
              Checking outbox queue...
            </div>
          </div>

          <div class="mt-sm pt-xs border-t caption text-muted">
            🛡️ Invariant: Queue is hard-capped at ${MAX_OUTBOX_CAP} items. Writes throw explicit error when full to guarantee zero silent drops.
          </div>
        `
      })}

      <!-- Conflicts Log & Resolution Surfacing -->
      ${renderCard({
        content: `
          <div class="flex-row justify-between items-center mb-sm">
            <div>
              <span class="label-md">Server Conflict Resolutions</span>
              <div class="caption text-muted">Handled and surfaced deterministically</div>
            </div>
            ${renderBadge(`${conflicts.length} Active`, conflicts.length > 0 ? 'warning' : 'primary')}
          </div>

          ${conflicts.length === 0 ? `
            <div class="text-center p-sm caption text-muted rounded bg-black-20">
              No unresolved conflicts. All local records match server invariants.
            </div>
          ` : `
            <div class="conflict-list">
              ${conflicts.map(c => `
                <div class="conflict-item ${c.resolution && c.resolution.includes('server_won') ? 'server-won' : ''}">
                  <div class="flex-row justify-between font-semibold">
                    <span class="text-primary">${c.title || c.type}</span>
                    ${renderBadge(c.resolution, 'secondary')}
                  </div>
                  <div class="text-secondary mt-2xs">${c.message}</div>
                  <div class="caption text-muted font-data mt-2xs">
                    Table: ${c.table} · ID: ${c.id}
                  </div>
                </div>
              `).join('')}
            </div>
            <div class="mt-sm flex-row justify-end">
              ${renderButton({
                text: 'Dismiss All Conflicts',
                variant: 'ghost',
                size: 'sm',
                action: 'clear-conflicts'
              })}
            </div>
          `}

          <!-- Conflict Simulation Buttons for Verification Testing -->
          <div class="mt-sm pt-sm border-t">
            <span class="caption text-muted block mb-xs">
              Simulate Server Conflict Scenarios:
            </span>
            <div class="grid-2-col gap-xs">
              ${renderButton({ text: '1. Merged as Update', variant: 'outline', size: 'sm', action: 'simulate-conflict', dataAttrs: 'data-conflict-type="merged_as_update"' })}
              ${renderButton({ text: '2. Last-Writer-Wins', variant: 'outline', size: 'sm', action: 'simulate-conflict', dataAttrs: 'data-conflict-type="server_won"' })}
              ${renderButton({ text: '3. Read-Only Table', variant: 'outline', size: 'sm', action: 'simulate-conflict', dataAttrs: 'data-conflict-type="server_authoritative"' })}
              ${renderButton({ text: '4. Active Lien Delete', variant: 'outline', size: 'sm', action: 'simulate-conflict', dataAttrs: 'data-conflict-type="delete_rejected"' })}
            </div>
          </div>
        `
      })}

      <!-- Auth Session & 401 Refresh Verification -->
      ${renderCard({
        content: `
          <div class="flex-row justify-between items-center mb-xs">
            <span class="label-md">Session Store & 401 Refresh</span>
            ${renderBadge('ACTIVE', 'success')}
          </div>
          <div class="caption text-muted font-data break-all">
            Token: ${(session.accessToken || '').substring(0, 24)}...<br>
            Refresh: ${(session.refreshToken || '').substring(0, 24)}...
          </div>
          <div class="mt-sm flex-row gap-sm">
            ${renderButton({
              text: 'Simulate 401 (Expire Access Token)',
              variant: 'outline',
              size: 'sm',
              action: 'simulate-token-expiry'
            })}
          </div>
        `
      })}

      <!-- Manual Verification Steps Accordion / Card -->
      ${renderCard({
        extraClasses: 'border-strong',
        content: `
          <span class="label-md text-accent mb-xs block">
            📋 Manual Verification Protocol
          </span>
          <ol class="verification-list">
            <li><strong>Airplane Mode:</strong> Click "✈️ Go Airplane Mode" above to simulate rural disconnection.</li>
            <li><strong>Write Offline:</strong> Go to "07 AI Grain Assay" or "Produce" and publish a new lot.</li>
            <li><strong>Confirm Local Truth:</strong> Verify the lot is saved immediately in local IndexedDB with status <code>OUTBOX</code> and queue count increases.</li>
            <li><strong>Reconnect & Sync:</strong> Click "📶 Reconnect Online" — sync engine automatically executes <em>pull first</em> (delta since watermark), then <em>pushes outbox</em>.</li>
            <li><strong>Verify Zero Data Loss:</strong> Confirm lot transitions to <code>SYNCED</code> with zero duplicates or data drops.</li>
          </ol>
        `
      })}
    </div>
  `;
}
