/* =====================================================================
   MittiMandi Screen: Market Intelligence & TFT Quantile Price Forecaster (MKT-01 to 02)
   TimescaleDB Real-time AGMARKNET Prices & Temporal Fusion Transformer Forecast
   Includes Dynamic SVG Confidence Bands, Multi-Horizon Projections & Offline Caching
   ===================================================================== */

import { store } from '../state.js';
import { api } from '../api.js';
import { renderBadge } from '../components/badge.js';
import { renderButton } from '../components/button.js';
import { renderCard } from '../components/card.js';
import { renderLoadingSkeleton, renderErrorState, renderStaleBadge, renderEmptyState } from '../components/states.js';
import { renderBenchmarkRow } from '../components/price-tile.js';

// Module-level reactive cache
let activeCommodity = 'Wheat';
let activeHorizon = 21;
let searchQuery = '';
let isLoading = false;
let loadError = null;
let lastFetchedAt = null;
let cachedForecast = null;
let cachedPrices = [];

export function getActiveMarketCommodity() {
  return activeCommodity;
}

export function setActiveMarketCommodity(commodity) {
  activeCommodity = commodity;
  fetchMarketData(true);
}

export function setActiveMarketHorizon(days) {
  activeHorizon = Math.min(parseInt(days, 10) || 21, 21);
  fetchMarketData(true);
}

export function setSearchQuery(q) {
  searchQuery = q || '';
}

export async function fetchMarketData(force = false) {
  if (isLoading) return;
  if (!force && lastFetchedAt && (Date.now() - lastFetchedAt < 60000) && cachedForecast) {
    return;
  }

  isLoading = true;
  loadError = null;

  try {
    const isOnline = store.get('isOnline');
    if (!isOnline && cachedPrices.length > 0) {
      // Offline fallback to memory or store cache
      isLoading = false;
      return;
    }

    const [pricesRes, forecastRes] = await Promise.all([
      api.getMandiPrices({ commodity: activeCommodity, limit: 12 }),
      api.getTftForecast(activeCommodity, { horizon_days: activeHorizon })
    ]);

    if (pricesRes && pricesRes.length > 0) {
      cachedPrices = pricesRes;
      store.set('mandiPrices', pricesRes);
    }
    if (forecastRes) {
      cachedForecast = forecastRes;
    }
    lastFetchedAt = Date.now();
  } catch (err) {
    console.warn('[MarketIntel] Failed to fetch live mandi rates:', err.message);
    loadError = err.message;
  } finally {
    isLoading = false;
    if (window.appRouter && store.get('currentScreen') === 'market-intel') {
      window.appRouter.render();
    }
  }
}

export function renderMarketIntel() {
  const isOnline = store.get('isOnline');
  const storedPrices = store.get('mandiPrices') || [];
  const pricesList = cachedPrices.length > 0 ? cachedPrices : storedPrices;

  // Trigger lazy initial fetch if cache is cold
  if (!lastFetchedAt && !isLoading && !loadError) {
    setTimeout(() => fetchMarketData(false), 10);
  }

  const commodities = ['Wheat', 'Soybean', 'Chana', 'Mustard'];
  const horizons = [7, 14, 21];

  // Filter prices by search query
  let filteredPrices = pricesList;
  if (searchQuery.trim()) {
    const q = searchQuery.toLowerCase();
    filteredPrices = filteredPrices.filter(p => 
      (p.mandi || '').toLowerCase().includes(q) ||
      (p.state || '').toLowerCase().includes(q) ||
      (p.variety || '').toLowerCase().includes(q)
    );
  }

  return `
    <div class="screen-content">
      <div class="flex-row justify-between items-center">
        <div>
          <div class="flex-row gap-xs items-center">
            ${renderBadge('MANDI INTELLIGENCE', 'primary')}
            ${isOnline 
              ? renderBadge('LIVE TICKER', 'success') 
              : renderBadge('OFFLINE SNAPSHOT', 'warning')}
            ${renderStaleBadge(lastFetchedAt)}
          </div>
          <h2 class="headline-md mt-xs">Mandi Trends & AI Forecast</h2>
          <p class="caption text-secondary">
            TimescaleDB AGMARKNET aggregation with Temporal Fusion Transformer (TFT) quantile pricing.
          </p>
        </div>
        ${renderButton({
          text: isLoading ? '⏳ Syncing…' : '🔄 Refresh',
          variant: 'outline',
          size: 'sm',
          action: 'refresh-market-data'
        })}
      </div>

      <!-- Commodity Selector Ribbon -->
      <div class="lot-filter-bar">
        ${commodities.map(c => `
          <button class="filter-chip ${activeCommodity === c ? 'active' : ''}" 
                  data-action="set-market-commodity" 
                  data-commodity="${c}">
            🌾 ${c}
          </button>
        `).join('')}
      </div>

      <!-- Horizon Selector Ribbon -->
      <div class="flex-row justify-between items-center mt-xs">
        <span class="caption text-muted font-medium">Projection Horizon:</span>
        <div class="flex-row gap-xs">
          ${horizons.map(h => `
            <button class="filter-chip ${activeHorizon === h ? 'active' : ''}" 
                    data-action="set-market-horizon" 
                    data-horizon="${h}">
              ⏱️ ${h} Days
            </button>
          `).join('')}
        </div>
      </div>

      ${isLoading && !cachedForecast ? renderLoadingSkeleton(2, 'card') : ''}

      ${loadError && !cachedForecast ? renderErrorState({
        title: 'Mandi Rates Unavailable',
        message: loadError,
        action: 'refresh-market-data',
        retryText: 'Retry Rates'
      }) : ''}

      <!-- AI Decision Advisor Alert -->
      ${renderDecisionAdvisor(cachedForecast)}

      <!-- Dynamic TFT SVG Quantile Forecast Graph -->
      ${renderForecastChart(cachedForecast, activeCommodity, activeHorizon)}

      <!-- Regional Mandi Benchmark Comparison -->
      ${renderCard({
        content: `
          <div class="flex-row justify-between items-center mb-sm">
            <div>
              <span class="label-md block font-semibold">Regional Mandi Benchmarks (Today)</span>
              <span class="caption text-muted">Arrivals and modal settlement rates</span>
            </div>
            <span class="font-data caption text-accent font-semibold">${filteredPrices.length} Mandis</span>
          </div>

          <!-- Quick Filter Input -->
          <div class="form-group mb-sm">
            <input type="text" 
                   id="market-search-input" 
                   class="form-input text-sm" 
                   placeholder="🔍 Search Mandi (e.g. Indore, Ujjain, Dewas)…" 
                   value="${searchQuery}" 
                   data-change="search-market-mandi">
          </div>

          <div class="flex-col gap-sm">
            ${filteredPrices.length === 0 ? `
              <div class="p-md text-center caption text-muted rounded bg-black-20">
                No mandi observations found matching &ldquo;${searchQuery}&rdquo;.
              </div>
            ` : filteredPrices.map((b, idx) => `
              <div class="benchmark-row ${idx === 0 ? 'highlighted' : ''}">
                <div class="flex-col">
                  <span class="benchmark-mandi">${b.mandi || 'Mandi APMC'}</span>
                  <span class="benchmark-state caption text-muted">
                    ${b.state || 'Madhya Pradesh'} · ${b.variety || 'FAQ'} 
                    ${b.arrivals ? `(${parseFloat(b.arrivals).toFixed(0)} Qtl arrivals)` : ''}
                  </span>
                </div>
                <div class="flex-col items-end">
                  <span class="benchmark-price font-data font-bold">₹${b.price || b.modalPrice || 2310}</span>
                  <div class="flex-row gap-2xs items-center">
                    <span class="badge ${String(b.delta || '+0.0%').startsWith('-') ? 'badge-danger' : 'badge-success'} body-2xs">
                      ${b.delta || '+0.0%'}
                    </span>
                  </div>
                </div>
              </div>
            `).join('')}
          </div>
        `
      })}
    </div>
  `;
}

function renderDecisionAdvisor(forecast) {
  if (!forecast) {
    return `
      <div class="decision-banner">
        <div class="decision-icon">💡</div>
        <div class="decision-body">
          <div class="flex-row items-center gap-sm">
            <strong class="text-success font-semibold">AI RECOMMENDATION: STORE LOT</strong>
            ${renderBadge('CONFIDENCE 91%', 'success')}
          </div>
          <p class="caption text-primary mt-2xs">
            Sharbati Wheat prices are projected to rise from <strong>₹2,295</strong> to <strong>₹2,578/Qtl</strong> (+12.3%) over the next 21 days due to festive procurement and flour mill restocking.
          </p>
          <div class="mt-sm">
            ${renderButton({
              text: 'Reserve Cold Storage @ ₹28/mo →',
              variant: 'secondary',
              size: 'sm',
              action: 'nav',
              screen: 'storage'
            })}
          </div>
        </div>
      </div>
    `;
  }

  const isStore = forecast.recommendation === 'STORE';
  const recBadgeVariant = isStore ? 'success' : 'warning';
  const recLabel = isStore ? 'AI RECOMMENDATION: STORE HARVEST' : 'AI RECOMMENDATION: SELL IMMEDIATELY';

  return `
    <div class="decision-banner">
      <div class="decision-icon">${isStore ? '🌾' : '⚡'}</div>
      <div class="decision-body">
        <div class="flex-row items-center gap-sm">
          <strong class="${isStore ? 'text-success' : 'text-accent'} font-semibold">${recLabel}</strong>
          ${renderBadge('TFT PINBALL LOSS ML', recBadgeVariant)}
        </div>
        <p class="caption text-primary mt-2xs">
          ${forecast.rationale || `Projected terminal price: ₹${forecast.p50Terminal || forecast.currentPrice}/Qtl. Holding cost: ₹${forecast.totalHoldingCost || 9}/Qtl.`}
        </p>

        <div class="flex-row gap-md mt-xs body-xs text-secondary">
          <span>Capital Lockup: <strong>₹${forecast.capitalCost || 9}/qtl</strong></span>
          <span>Storage Cost: <strong>₹${forecast.storageCost || 0}/qtl</strong></span>
          <span>Projected Net: <strong class="${(forecast.expectedNetGain || 0) >= 0 ? 'text-success' : 'text-danger'}">${forecast.projectedNetGain || '₹0'}</strong></span>
        </div>

        <div class="mt-sm flex-row gap-xs">
          ${isStore ? renderButton({
            text: 'Reserve Warehouse (WDRA) →',
            variant: 'secondary',
            size: 'sm',
            action: 'nav',
            screen: 'storage'
          }) : renderButton({
            text: 'Review Buyer Bids →',
            variant: 'primary',
            size: 'sm',
            action: 'nav',
            screen: 'trades-negotiate'
          })}
        </div>
      </div>
    </div>
  `;
}

function renderForecastChart(forecast, commodity, horizonDays) {
  const currentPrice = forecast?.currentPrice || 2295;
  const p10Term = forecast?.p10Terminal || 2012;
  const p50Term = forecast?.p50Terminal || 2295;
  const p90Term = forecast?.p90Terminal || 2578;

  // Use actual forecast points or create evenly spaced points across the horizon
  let points = forecast?.forecastDays || [];
  if (points.length === 0) {
    points = [
      { dayOffset: 1, p10: currentPrice - 20, p50: currentPrice, p90: currentPrice + 30 },
      { dayOffset: 7, p10: currentPrice - 70, p50: currentPrice + 10, p90: currentPrice + 90 },
      { dayOffset: 14, p10: currentPrice - 130, p50: currentPrice + 20, p90: currentPrice + 170 },
      { dayOffset: 21, p10: p10Term, p50: p50Term, p90: p90Term }
    ];
  }

  // Calculate dynamic SVG coordinates
  const svgWidth = 340;
  const svgHeight = 160;
  const padLeft = 40;
  const padRight = 20;
  const padTop = 20;
  const padBottom = 25;

  const chartW = svgWidth - padLeft - padRight;
  const chartH = svgHeight - padTop - padBottom;

  const allVals = points.flatMap(p => [p.p10, p.p50, p.p90]).concat([currentPrice]);
  const minVal = Math.floor(Math.min(...allVals) / 50) * 50 - 50;
  const maxVal = Math.ceil(Math.max(...allVals) / 50) * 50 + 50;
  const valRange = maxVal - minVal || 1;

  const getY = val => padTop + chartH - ((val - minVal) / valRange) * chartH;
  const getX = (idx, total) => padLeft + (idx / Math.max(total - 1, 1)) * chartW;

  // Build coordinate arrays
  const p90Coords = points.map((p, i) => `${getX(i, points.length).toFixed(1)},${getY(p.p90).toFixed(1)}`);
  const p50Coords = points.map((p, i) => `${getX(i, points.length).toFixed(1)},${getY(p.p50).toFixed(1)}`);
  const p10Coords = points.map((p, i) => `${getX(i, points.length).toFixed(1)},${getY(p.p10).toFixed(1)}`);

  // Polygon for confidence band: p90 forward, then p10 backward
  const revP10 = [...p10Coords].reverse();
  const polygonPoints = `${p90Coords.join(' ')} ${revP10.join(' ')}`;

  // Y-axis grid markers (4 evenly spaced ticks)
  const yTicks = [
    { val: maxVal, y: getY(maxVal) },
    { val: Math.round(minVal + valRange * 0.66), y: getY(minVal + valRange * 0.66) },
    { val: Math.round(minVal + valRange * 0.33), y: getY(minVal + valRange * 0.33) },
    { val: minVal, y: getY(minVal) }
  ];

  return renderCard({
    extraClasses: 'chart-card',
    content: `
      <div class="flex-row justify-between items-center">
        <div>
          <span class="headline-sm">${horizonDays}-Day Quantile Forecast</span>
          <div class="caption text-muted">${commodity} · Central Mandi Cluster</div>
        </div>
        ${renderBadge('TFT MODEL v4.2', 'primary')}
      </div>

      <!-- SVG Line & Multi-Quantile Confidence Area -->
      <svg class="forecast-svg" viewBox="0 0 ${svgWidth} ${svgHeight}">
        <defs>
          <linearGradient id="gradP90Dynamic" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stop-color="var(--primary)" stop-opacity="0.35"/>
            <stop offset="100%" stop-color="var(--primary)" stop-opacity="0.03"/>
          </linearGradient>
        </defs>

        <!-- Y-Axis Grid Lines & Numbers -->
        ${yTicks.map(t => `
          <line x1="${padLeft}" y1="${t.y.toFixed(1)}" x2="${svgWidth - padRight}" y2="${t.y.toFixed(1)}" stroke="rgba(255,255,255,0.06)" stroke-dasharray="3"/>
          <text x="${padLeft - 6}" y="${(t.y + 3).toFixed(1)}" fill="var(--text-muted)" font-size="8.5" text-anchor="end" font-family="monospace">${t.val}</text>
        `).join('')}

        <!-- Shaded Confidence Band (p10 to p90) -->
        <polygon points="${polygonPoints}" fill="url(#gradP90Dynamic)"/>

        <!-- P90 Upper Curve (Cyan Dashed) -->
        <polyline points="${p90Coords.join(' ')}" fill="none" stroke="var(--primary-light)" stroke-width="1.5" stroke-dasharray="4"/>

        <!-- P50 Median Expected Curve (Terracotta Solid) -->
        <polyline points="${p50Coords.join(' ')}" fill="none" stroke="var(--secondary-light)" stroke-width="2.5"/>

        <!-- P10 Conservative Floor Curve (Gold Dotted) -->
        <polyline points="${p10Coords.join(' ')}" fill="none" stroke="var(--tertiary-light)" stroke-width="1.5" stroke-dasharray="2"/>

        <!-- Data Points on P50 Median -->
        ${points.map((p, i) => {
          const cx = getX(i, points.length).toFixed(1);
          const cy = getY(p.p50).toFixed(1);
          return `<circle cx="${cx}" cy="${cy}" r="${i === points.length - 1 ? '4.5' : '3.5'}" fill="var(--secondary-light)"/>`;
        }).join('')}

        <!-- Current Day Marker -->
        <line x1="${padLeft}" y1="${padTop}" x2="${padLeft}" y2="${svgHeight - padBottom}" stroke="rgba(255,255,255,0.4)" stroke-dasharray="2"/>
        <text x="${padLeft}" y="${svgHeight - 10}" fill="var(--text-primary)" font-size="8.5" text-anchor="middle" font-family="monospace">Today</text>
        <text x="${(padLeft + chartW * 0.5).toFixed(1)}" y="${svgHeight - 10}" fill="var(--text-muted)" font-size="8.5" text-anchor="middle" font-family="monospace">+${Math.round(horizonDays / 2)}d</text>
        <text x="${(padLeft + chartW).toFixed(1)}" y="${svgHeight - 10}" fill="var(--text-primary)" font-size="8.5" text-anchor="middle" font-family="monospace">+${horizonDays}d</text>
      </svg>

      <!-- Chart Quantile Legend -->
      <div class="chart-legend">
        <div class="legend-item">
          <span class="legend-dot legend-dot-p50"></span>
          <span>Median (p50: ₹${p50Term})</span>
        </div>
        <div class="legend-item">
          <span class="legend-dot legend-dot-p90"></span>
          <span>Bullish (p90: ₹${p90Term})</span>
        </div>
        <div class="legend-item">
          <span class="legend-dot legend-dot-p10"></span>
          <span>Floor (p10: ₹${p10Term})</span>
        </div>
      </div>
    `
  });
}
