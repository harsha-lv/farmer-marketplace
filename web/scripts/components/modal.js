/* =====================================================================
   MittiMandi Shared Component: Accessible Modal Dialog
   Replaces blocking browser alert() and confirm()
   Features: Focus trap, Escape key handling, Promise-based async API
   ===================================================================== */

export function showModal({
  title = 'Confirmation',
  message = '',
  confirmText = 'Confirm',
  cancelText = 'Cancel',
  isDanger = false,
  isAlert = false
} = {}) {
  return new Promise((resolve) => {
    // Remove any existing active modal
    const existing = document.getElementById('app-modal-root');
    if (existing) existing.remove();

    const root = document.createElement('div');
    root.id = 'app-modal-root';
    root.className = 'modal-backdrop';
    root.setAttribute('role', 'dialog');
    root.setAttribute('aria-modal', 'true');
    root.setAttribute('aria-labelledby', 'modal-title');
    root.setAttribute('aria-describedby', 'modal-description');

    root.innerHTML = `
      <div class="modal-dialog">
        <div class="modal-header">
          <h3 id="modal-title" class="headline-sm">${title}</h3>
          <button type="button" class="modal-close-btn" id="modal-close-btn" aria-label="Close dialog">✕</button>
        </div>
        <div class="modal-body" id="modal-description">
          <p class="body-md">${message}</p>
        </div>
        <div class="modal-actions">
          ${!isAlert ? `
            <button type="button" class="btn btn-outline btn-md" id="modal-cancel-btn">
              <span>${cancelText}</span>
            </button>
          ` : ''}
          <button type="button" class="btn ${isDanger ? 'btn-danger' : 'btn-primary'} btn-md" id="modal-confirm-btn">
            <span>${confirmText}</span>
          </button>
        </div>
      </div>
    `;

    document.body.appendChild(root);

    const confirmBtn = root.querySelector('#modal-confirm-btn');
    const cancelBtn = root.querySelector('#modal-cancel-btn');
    const closeBtn = root.querySelector('#modal-close-btn');

    // Focus primary action
    confirmBtn?.focus();

    function cleanup(result) {
      document.removeEventListener('keydown', handleKeyDown);
      root.classList.remove('modal-open');
      setTimeout(() => root.remove(), 150);
      resolve(result);
    }

    function handleKeyDown(e) {
      if (e.key === 'Escape') {
        e.preventDefault();
        cleanup(false);
      }
      // Simple focus trap
      if (e.key === 'Tab') {
        const focusables = root.querySelectorAll('button:not([disabled])');
        if (focusables.length === 0) return;
        const first = focusables[0];
        const last = focusables[focusables.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    }

    document.addEventListener('keydown', handleKeyDown);

    confirmBtn?.addEventListener('click', () => cleanup(true));
    cancelBtn?.addEventListener('click', () => cleanup(false));
    closeBtn?.addEventListener('click', () => cleanup(false));
    root.addEventListener('click', (e) => {
      if (e.target === root) cleanup(false);
    });

    // Animate entrance
    requestAnimationFrame(() => root.classList.add('modal-open'));
  });
}

export function modalAlert(message, title = 'Notice') {
  return showModal({ title, message, confirmText: 'OK', isAlert: true });
}

export function modalConfirm(message, title = 'Please Confirm', isDanger = false) {
  return showModal({ title, message, isDanger, isAlert: false });
}
