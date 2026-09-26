/* =====================================================================
   MittiMandi Shared Component: Standard UI States
   Loading Skeletons, Empty States, Error States with Retry, Stale Badges
   CSP-Safe: uses declarative data-action and data-screen attributes
   ===================================================================== */

export function renderLoadingSkeleton(count = 2, type = 'card') {
  const items = Array.from({ length: count }).map(() => `
    <div class="skeleton-item skeleton-${type}" aria-busy="true" aria-live="polite">
      <div class="skeleton-line skeleton-title"></div>
      <div class="skeleton-line skeleton-body"></div>
      <div class="skeleton-line skeleton-caption"></div>
    </div>
  `).join('');

  return `<div class="skeleton-container">${items}</div>`;
}

export function renderEmptyState({
  icon = '🌾',
  title = 'No Records Found',
  message = 'There is currently no data to display.',
  ctaText = '',
  action = '',
  screen = '',
  onCta = ''
} = {}) {
  let resolvedAction = action || onCta;
  let resolvedScreen = screen;

  if (resolvedAction && typeof resolvedAction === 'string') {
    if (resolvedAction.includes('navigate(')) {
      const m = resolvedAction.match(/navigate\(['"]([^'"]+)['"]\)/);
      resolvedAction = 'nav';
      if (m) resolvedScreen = m[1];
    } else if (resolvedAction === 'lots-create' || resolvedAction === 'lots-list' || resolvedAction === 'dashboard') {
      resolvedScreen = resolvedAction;
      resolvedAction = 'nav';
    } else if (resolvedAction.includes('showToast(')) {
      const m = resolvedAction.match(/showToast\(['"]([^'"]+)['"]\)/);
      resolvedAction = 'toast';
      return `
        <div class="empty-state-card" role="status">
          <div class="empty-state-icon" aria-hidden="true">${icon}</div>
          <h3 class="headline-sm empty-state-title">${title}</h3>
          <p class="caption text-muted empty-state-msg">${message}</p>
          ${ctaText ? `
            <div class="empty-state-action">
              <button type="button" class="btn btn-primary btn-sm" data-action="toast" data-toast-msg="${m ? m[1].replace(/"/g, '&quot;') : ''}">
                <span>${ctaText}</span>
              </button>
            </div>
          ` : ''}
        </div>
      `;
    }
  }

  const actionAttr = resolvedAction ? `data-action="${resolvedAction}"` : '';
  const screenAttr = resolvedScreen ? `data-screen="${resolvedScreen}"` : '';

  return `
    <div class="empty-state-card" role="status">
      <div class="empty-state-icon" aria-hidden="true">${icon}</div>
      <h3 class="headline-sm empty-state-title">${title}</h3>
      <p class="caption text-muted empty-state-msg">${message}</p>
      ${ctaText && resolvedAction ? `
        <div class="empty-state-action">
          <button type="button" class="btn btn-primary btn-sm" ${actionAttr} ${screenAttr}>
            <span>${ctaText}</span>
          </button>
        </div>
      ` : ''}
    </div>
  `;
}

export function renderErrorState({
  title = 'Failed to load data',
  message = 'A network or server error occurred. Please try again.',
  action = 'manual-sync',
  onRetry = '',
  retryText = 'Retry Now'
} = {}) {
  const resolvedAction = action || (onRetry ? 'manual-sync' : '');
  return `
    <div class="error-state-card" role="alert">
      <div class="error-state-icon" aria-hidden="true">⚠️</div>
      <h3 class="headline-sm error-state-title">${title}</h3>
      <p class="caption text-muted error-state-msg">${message}</p>
      ${resolvedAction ? `
        <div class="error-state-action">
          <button type="button" class="btn btn-secondary btn-sm" data-action="${resolvedAction}">
            <span>🔄 ${retryText}</span>
          </button>
        </div>
      ` : ''}
    </div>
  `;
}

export function renderStaleBadge(timestamp = null) {
  if (!timestamp) return '';
  const timeStr = new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  return `
    <span class="stale-cache-badge" title="Data cached locally at ${new Date(timestamp).toLocaleString()}">
      <span>⏱️ Cached ${timeStr}</span>
    </span>
  `;
}
