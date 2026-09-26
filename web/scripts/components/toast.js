/* =====================================================================
   MittiMandi Shared Component: Notifications & Persistent Banner
   Single unified notification system for ephemeral toasts & sync banners
   ===================================================================== */

let toastTimeout = null;

export function showToast(message, type = 'info', duration = 3500) {
  let toast = document.getElementById('global-toast');
  if (!toast) {
    toast = document.createElement('div');
    toast.id = 'global-toast';
    toast.className = 'toast-notice';
    toast.setAttribute('role', 'status');
    toast.setAttribute('aria-live', 'polite');
    const container = document.getElementById('device-frame') || document.body;
    container.appendChild(toast);
  }

  const iconMap = {
    info: '✨',
    success: '✓',
    warning: '⚠️',
    danger: '❌'
  };
  const icon = iconMap[type] || '✨';

  const esc = s => (s||'').toString().replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  toast.innerHTML = `<span class="toast-icon">${icon}</span><span class="toast-text">${esc(message)}</span>`;
  toast.className = `toast-notice toast-${type}`;
  toast.style.display = 'flex';

  clearTimeout(toastTimeout);
  toastTimeout = setTimeout(() => {
    toast.style.display = 'none';
  }, duration);
}

// Global exposure for backward compatibility with onclick handlers
if (typeof window !== 'undefined') {
  window.showToast = showToast;
}

export function renderPersistentIndicator(show, text = '', onRetry = null) {
  if (typeof document === 'undefined') return;
  let banner = document.getElementById('sync-persistent-indicator');

  if (!show) {
    if (banner) banner.style.display = 'none';
    return;
  }

  if (!banner) {
    banner = document.createElement('div');
    banner.id = 'sync-persistent-indicator';
    banner.className = 'sync-persistent-banner';
    banner.setAttribute('role', 'alert');
    banner.setAttribute('aria-live', 'assertive');
    const frame = document.getElementById('device-frame') || document.body;
    frame.appendChild(banner);
  }

  banner.innerHTML = `
    <span class="banner-icon">⚠️</span>
    <span class="banner-text">${text}</span>
    <button type="button" class="btn btn-danger btn-sm banner-retry-btn" id="sync-banner-retry-btn" data-action="manual-sync">
      <span>Retry now</span>
    </button>
  `;
  banner.style.display = 'flex';

  const retryBtn = banner.querySelector('#sync-banner-retry-btn');
  if (retryBtn) {
    retryBtn.addEventListener('click', () => {
      if (typeof onRetry === 'function') {
        onRetry();
      } else if (typeof window.triggerManualSync === 'function') {
        window.triggerManualSync();
      } else if (window.syncEngine && typeof window.syncEngine.triggerSync === 'function') {
        window.syncEngine.triggerSync();
      }
    });
  }
}
