/* =====================================================================
   MittiMandi Shared Component: Card & Metric Blocks
   Standard card containers, interactive cards, and tabular metric blocks
   CSP-Safe: uses data-action instead of inline event handlers
   ===================================================================== */

export function renderCard({
  content = '',
  variant = 'default', // default, interactive, primary-gradient, gold-gradient, recommendation
  extraClasses = '',
  action = '',
  screen = '',
  onClick = '',
  id = ''
} = {}) {
  let resolvedAction = action || onClick;
  let resolvedScreen = screen;

  if (resolvedAction && typeof resolvedAction === 'string') {
    if (resolvedAction.includes('navigate(')) {
      const m = resolvedAction.match(/navigate\(['"]([^'"]+)['"]\)/);
      resolvedAction = 'nav';
      if (m) resolvedScreen = m[1];
    } else if (resolvedAction === 'lots-list' || resolvedAction === 'dashboard') {
      resolvedScreen = resolvedAction;
      resolvedAction = 'nav';
    }
  }

  const isInteractive = Boolean(resolvedAction);
  const classes = [
    'card',
    variant !== 'default' ? `card-${variant}` : '',
    isInteractive ? 'card-interactive' : '',
    extraClasses
  ].filter(Boolean).join(' ');

  const actionAttr = resolvedAction ? `data-action="${resolvedAction}"` : '';
  const screenAttr = resolvedScreen ? `data-screen="${resolvedScreen}"` : '';
  const idAttr = id ? `id="${id}"` : '';

  return `<div class="${classes}" ${actionAttr} ${screenAttr} ${idAttr}>${content}</div>`;
}

export function renderMetricBlock({
  label = '',
  value = '',
  subtext = '',
  valueClass = 'data-sm',
  align = 'left'
} = {}) {
  return `
    <div class="metric-block text-${align}">
      <span class="caption text-muted">${label}</span>
      <div class="${valueClass}">${value}</div>
      ${subtext ? `<span class="caption text-secondary">${subtext}</span>` : ''}
    </div>
  `;
}

export function renderDataRow(label, value, valueClass = 'data-sm') {
  return `
    <div class="data-row">
      <span class="caption text-muted">${label}</span>
      <strong class="${valueClass}">${value}</strong>
    </div>
  `;
}
