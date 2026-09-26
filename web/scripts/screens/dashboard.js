/* =====================================================================
   MittiMandi Screen: Farmer Dashboard & Net Realization Overview
   Migrated onto shared component library (F1 Foundation)
   ===================================================================== */

import { store } from '../state.js';
import { renderBadge, renderGradeBadge } from '../components/badge.js';
import { renderPriceTickerStrip } from '../components/price-tile.js';
import { renderCard } from '../components/card.js';
import { renderEmptyState } from '../components/states.js';
import { renderButton } from '../components/button.js';
import { renderKycChip } from '../components/status-chip.js';

export function renderDashboard() {
  const user = store.get('user');
  const mandiPrices = store.get('mandiPrices') || [];
  const lots = store.get('lots') || [];

  return `
    <div class="screen-content">
      <!-- Top Welcome & Location Banner -->
      <div class="flex-row justify-between items-start">
        <div>
          <div class="flex-row items-center gap-sm">
            <span class="headline-md">नमस्ते, ${user.name}</span>
            ${renderKycChip('verified')}
          </div>
          <p class="caption text-secondary mt-xs">
            📍 ${user.location} · <em>${user.fpo}</em>
          </p>
        </div>
        <button class="icon-btn" data-action="nav" data-screen="offline-sync" title="Sync Status">
          <span>📶</span>
        </button>
      </div>

      <!-- Weather Advisory Widget -->
      <div class="weather-widget">
        <div class="weather-info">
          <span class="caption text-secondary">Agri-Weather Forecast</span>
          <div class="weather-temp">
            <span>29°C</span>
            <span class="caption text-secondary font-regular">Partly Cloudy</span>
          </div>
          <div class="weather-advisory">
            <span>🌾 Optimal harvesting window next 48 hrs. Keep harvested lots covered.</span>
          </div>
        </div>
        <div class="weather-icon">⛅</div>
      </div>

      <!-- Live Mandi Prices Strip -->
      <div>
        <div class="flex-row justify-between items-center mb-sm">
          <span class="label-md text-primary">Live Mandi Rates / मंडी भाव</span>
          ${renderButton({
            text: 'Deep Forecast →',
            variant: 'ghost',
            size: 'sm',
            extraClasses: 'text-accent',
            action: 'nav',
            screen: 'market-intel'
          })}
        </div>

        ${renderPriceTickerStrip(mandiPrices)}
      </div>

      <!-- Net Realization Comparison Card (Interactive) -->
      ${renderCard({
        variant: 'gold-gradient',
        extraClasses: 'realization-box',
        content: `
          <div class="realization-header">
            <div>
              ${renderBadge('NET REALIZATION ADVISOR', 'tertiary')}
              <h3 class="headline-sm mt-xs">Mandi APMC vs MittiMandi Direct</h3>
            </div>
            <span class="realization-icon">⚖️</span>
          </div>

          <div class="realization-compare-grid">
            <div class="compare-col">
              <span class="compare-title">Traditional Mandi (100 Qtl)</span>
              <div class="compare-val mandi">₹2,58,000</div>
              <span class="caption text-muted">-6% commission, cess & transport cut</span>
            </div>
            <div class="compare-col compare-col-divider">
              <span class="compare-title">MittiMandi Direct Net</span>
              <div class="compare-val mitti">₹2,85,000</div>
              <span class="caption text-success">0% commission + locked freight quote</span>
            </div>
          </div>

          <div class="realization-gain">
            <span>Extra Income for Farmer:</span>
            <strong class="data-sm text-gold">+₹27,000 (+10.5%)</strong>
          </div>
        `
      })}

      <!-- Quick Actions Grid -->
      <div>
        <span class="label-md text-primary mb-sm block">Quick Actions</span>
        <div class="quick-actions-row">
          <div class="quick-action-btn" data-action="nav" data-screen="lots-create">
            <div class="quick-action-icon action-icon-primary">📷</div>
            <span class="quick-action-label">Add Lot & AI Assay</span>
          </div>
          <div class="quick-action-btn" data-action="nav" data-screen="market-intel">
            <div class="quick-action-icon action-icon-tertiary">📈</div>
            <span class="quick-action-label">Price Forecast</span>
          </div>
          <div class="quick-action-btn" data-action="nav" data-screen="trades-negotiate">
            <div class="quick-action-icon action-icon-secondary">🤝</div>
            <span class="quick-action-label">Active Bids</span>
          </div>
          <div class="quick-action-btn" data-action="nav" data-screen="transport">
            <div class="quick-action-icon action-icon-success">🚚</div>
            <span class="quick-action-label">Book Transit</span>
          </div>
        </div>
      </div>

      <!-- Active Produce Lots Summary -->
      <div>
        <div class="flex-row justify-between items-center mb-sm">
          <span class="label-md text-primary">My Listed Harvest Lots (${lots.length})</span>
          ${renderButton({
            text: 'View All →',
            variant: 'ghost',
            size: 'sm',
            extraClasses: 'text-accent',
            action: 'nav',
            screen: 'lots-list'
          })}
        </div>

        <div class="flex-col gap-sm">
          ${lots.length === 0 ? renderEmptyState({
            icon: '🌾',
            title: 'No Harvest Lots Listed',
            message: 'You have not registered any produce lots yet. Grade and list grain with AI assay.',
            ctaText: '+ Register Produce Lot',
            action: 'nav',
            screen: 'lots-create'
          }) : lots.map(lot => renderCard({
            variant: 'interactive',
            action: 'nav',
            screen: 'lots-list',
            content: `
              <div class="flex-row justify-between items-start">
                <div>
                  <span class="headline-sm">${lot.crop}</span>
                  <div class="caption text-muted font-data mt-xs">
                    ${lot.id} · ${lot.variety}
                  </div>
                </div>
                ${renderGradeBadge(lot.grade || 'Grade A')}
              </div>

              <div class="lot-metrics-strip mt-md pt-sm border-t">
                <div>
                  <span class="caption text-muted">Quantity</span>
                  <div class="data-sm">${lot.quantity} Quintals</div>
                </div>
                <div>
                  <span class="caption text-muted">Target Price</span>
                  <div class="data-sm text-primary">₹${lot.pricePerQtl}/Qtl</div>
                </div>
                <div class="text-right">
                  <span class="caption text-muted">Highest Offer</span>
                  <div class="data-sm text-success">₹${lot.highestBid || lot.pricePerQtl}/Qtl (${lot.bidsCount || 0} bids)</div>
                </div>
              </div>
            `
          })).join('')}
        </div>
      </div>
    </div>
  `;
}
