/* =====================================================================
   MittiMandi Shared Component: Price Tile & Ticker Strip
   Authoritative: Rural Commerce Material Baseline
   Features: IBM Plex Mono tabular numerals, Provenance Badges,
   Neutral price drops (NEVER Danger color).
   CSP-Safe: uses data-action instead of inline onclick
   ===================================================================== */

import { renderProvenanceBadge } from './badge.js';

export function renderPriceTile({
  crop = 'Crop',
  variety = 'Standard',
  mandi = 'APMC',
  price = 0,
  delta = '+0.0%',
  trend = 'up',
  provenance = 'Actual',
  unit = '/Qtl',
  action = '',
  screen = ''
} = {}) {
  const isUp = trend === 'up' || (typeof delta === 'string' && delta.startsWith('+'));
  let resolvedAction = action;
  let resolvedScreen = screen;
  if (resolvedAction && resolvedAction.includes('navigate(')) {
    const m = resolvedAction.match(/navigate\(['"]([^'"]+)['"]\)/);
    resolvedAction = 'nav';
    if (m) resolvedScreen = m[1];
  }
  const actionAttr = resolvedAction ? `data-action="${resolvedAction}"` : '';
  const screenAttr = resolvedScreen ? `data-screen="${resolvedScreen}"` : '';

  return `
    <div class="ticker-item ${resolvedAction ? 'interactive' : ''}" ${actionAttr} ${screenAttr}>
      <div class="ticker-crop">
        <div class="flex-row justify-between items-center">
          <span class="crop-name">${crop.split(' ')[0]}</span>
          ${renderProvenanceBadge(provenance)}
        </div>
        <span class="crop-variety">${variety}</span>
      </div>
      <div class="ticker-price data-md tabular-nums">
        ₹${Number(price).toLocaleString()} <span class="caption text-muted font-regular">${unit}</span>
      </div>
      <div class="ticker-delta ${isUp ? 'up' : 'neutral'}">
        <span>${isUp ? '▲' : '▼'}</span>
        <span>${delta}</span>
        <span class="ticker-mandi">${mandi.split(' ')[0]}</span>
      </div>
    </div>
  `;
}

export function renderPriceTickerStrip(prices = []) {
  if (!prices || prices.length === 0) {
    return `<div class="empty-ticker caption text-muted p-sm">No live mandi rates available.</div>`;
  }
  return `
    <div class="mandi-ticker-strip">
      ${prices.map(p => renderPriceTile(p)).join('')}
    </div>
  `;
}

export function renderBenchmarkRow({
  marketName = '',
  state = '',
  price = 0,
  delta = '+0.0%',
  provenance = 'Actual',
  isHighlighted = false
} = {}) {
  const isUp = typeof delta === 'string' && delta.startsWith('+');
  return `
    <div class="benchmark-row ${isHighlighted ? 'highlight' : ''}">
      <div class="benchmark-market">
        <div class="flex-row items-center gap-xs">
          <span>${marketName}</span>
          ${renderProvenanceBadge(provenance)}
        </div>
        ${state ? `<span class="caption text-muted">(${state})</span>` : ''}
      </div>
      <strong class="data-sm tabular-nums benchmark-price ${isUp ? 'trend-up' : 'trend-down'}">
        ₹${Number(price).toLocaleString()}/Qtl (${isUp ? '▲' : '▼'} ${delta})
      </strong>
    </div>
  `;
}
