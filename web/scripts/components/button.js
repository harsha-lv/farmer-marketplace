/* =====================================================================
   MittiMandi Shared Component: Button
   Pure tokenized HTML template function with loading state
   CSP-Safe: uses data-action instead of inline event handlers
   ===================================================================== */

export function renderButton({
  text = 'Submit',
  action = '',
  screen = '',
  onClick = '',
  variant = 'primary', // primary, secondary, tertiary, outline, ghost, danger
  size = 'md',        // sm, md, lg
  isBlock = false,
  disabled = false,
  isLoading = false,
  icon = null,
  extraClasses = '',
  id = '',
  type = 'button',
  dataAttrs = ''
} = {}) {
  const classes = [
    'btn',
    `btn-${variant}`,
    `btn-${size}`,
    isBlock ? 'btn-block' : '',
    isLoading ? 'btn-loading' : '',
    extraClasses
  ].filter(Boolean).join(' ');

  let resolvedAction = action || onClick;
  let resolvedScreen = screen;
  let extraData = dataAttrs;

  // Normalize any legacy JS strings to pure semantic data attributes
  if (resolvedAction && typeof resolvedAction === 'string') {
    if (resolvedAction.includes('navigate(')) {
      const m = resolvedAction.match(/navigate\(['"]([^'"]+)['"]\)/);
      resolvedAction = 'nav';
      if (m) resolvedScreen = m[1];
    } else if (resolvedAction.includes('goBack()')) {
      resolvedAction = 'back';
    } else if (resolvedAction.includes('render()')) {
      resolvedAction = 'render';
    } else if (resolvedAction.includes('showToast(')) {
      const m = resolvedAction.match(/showToast\(['"]([^'"]+)['"]\)/);
      resolvedAction = 'toast';
      if (m) extraData += ` data-toast-msg="${m[1].replace(/"/g, '&quot;')}"`;
    } else if (resolvedAction.includes('handleDeleteLot(')) {
      const m = resolvedAction.match(/handleDeleteLot\(['"]([^'"]+)['"]\)/);
      resolvedAction = 'delete-lot';
      if (m) extraData += ` data-lot-id="${m[1]}"`;
    } else if (resolvedAction.includes('simulateConflict(')) {
      const m = resolvedAction.match(/simulateConflict\(['"]([^'"]+)['"]\)/);
      resolvedAction = 'simulate-conflict';
      if (m) extraData += ` data-conflict-type="${m[1]}"`;
    } else if (resolvedAction.startsWith('window.')) {
      const fn = resolvedAction.replace(/^window\./, '').replace(/\(\)$/, '');
      const map = {
        handleSendOtp: 'send-otp',
        handleVerifyOtp: 'verify-otp',
        handleCreateLot: 'create-lot',
        handleSendCounterOffer: 'send-counter-offer',
        handleConfirmTransport: 'confirm-transport',
        toggleAirplaneMode: 'toggle-airplane',
        triggerManualSync: 'manual-sync',
        clearConflictsLog: 'clear-conflicts',
        simulateTokenExpiry: 'simulate-token-expiry',
        triggerAssay: 'trigger-assay'
      };
      resolvedAction = map[fn] || fn;
    }
  }

  const actionAttr = resolvedAction && !disabled && !isLoading ? `data-action="${resolvedAction}"` : '';
  const screenAttr = resolvedScreen ? `data-screen="${resolvedScreen}"` : '';
  const disabledAttr = disabled || isLoading ? 'disabled' : '';
  const idAttr = id ? `id="${id}"` : '';

  const content = isLoading
    ? `<span class="btn-spinner" aria-hidden="true"></span><span>Loading…</span>`
    : `${icon ? `<span class="btn-icon">${icon}</span>` : ''}<span>${text}</span>`;

  return `<button type="${type}" class="${classes}" ${actionAttr} ${screenAttr} ${extraData} ${disabledAttr} ${idAttr}>${content}</button>`;
}
