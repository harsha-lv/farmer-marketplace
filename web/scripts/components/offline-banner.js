/* =====================================================================
   MittiMandi Shared Component: Global Offline & Conflict Banner (F8)
   Uses store.get('isOnline') and store.get('conflicts') as single source of truth
   ===================================================================== */

import { store } from '../state.js';

export function renderGlobalOfflineBanner() {
  const isOnline = store.get('isOnline');
  const conflicts = store.get('conflicts') || [];

  if (isOnline && conflicts.length === 0) {
    return '';
  }

  let html = '';

  if (!isOnline) {
    html += `
      <div class="offline-global-banner" role="status" aria-live="polite">
        <div class="flex-row items-center gap-xs">
          <span>✈️</span>
          <span class="body-xs font-semibold">Offline Mode</span>
        </div>
        <span class="caption text-secondary">Local IndexedDB active. Writes buffered in outbox.</span>
      </div>
    `;
  }

  if (conflicts.length > 0) {
    html += `
      <div class="conflict-global-banner" role="alert">
        <div class="flex-row items-center gap-xs">
          <span>⚠️</span>
          <span class="body-xs font-semibold">${conflicts.length} Conflict(s) Surfaced</span>
        </div>
        <button class="btn btn-ghost btn-xs text-accent font-data" data-action="nav" data-screen="offline-sync">
          Review Hub →
        </button>
      </div>
    `;
  }

  return html;
}
