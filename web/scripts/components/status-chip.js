/* =====================================================================
   MittiMandi Shared Component: Status Chip
   Compact status indicators (network, outbox, lien, KYC)
   ===================================================================== */

export function renderStatusChip(text, type = 'info', icon = '') {
  return `
    <span class="status-chip chip-${type}">
      ${icon ? `<span class="chip-icon">${icon}</span>` : ''}
      <span>${text}</span>
    </span>
  `;
}

export function renderConnectionChip(isOnline) {
  const type = isOnline ? 'success' : 'danger';
  const icon = isOnline ? '📶' : '✈️';
  const text = isOnline ? 'Online (5G / WiFi)' : 'Airplane Mode (Offline)';
  return renderStatusChip(text, type, icon);
}

export function renderOutboxChip(pendingCount = 0, maxCap = 1000) {
  const type = pendingCount > 800 ? 'danger' : pendingCount > 0 ? 'warning' : 'success';
  const text = `${pendingCount} / ${maxCap} Queued`;
  return renderStatusChip(text, type, '⏳');
}

export function renderKycChip(isVerified = false) {
  return isVerified
    ? renderStatusChip('KYC Verified', 'success', '✓')
    : renderStatusChip('KYC Pending', 'warning', '⚠');
}
