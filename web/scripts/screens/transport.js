/* =====================================================================
   MittiMandi Screen: ONDC Transport Aggregation & Logistics Booking
   Migrated onto shared component library (F1 Foundation)
   ===================================================================== */

import { store } from '../state.js';
import { renderBadge } from '../components/badge.js';
import { renderButton } from '../components/button.js';
import { renderCard } from '../components/card.js';
import { renderEmptyState } from '../components/states.js';

export function renderTransport() {
  const transports = store.get('transports') || [];
  const selected = store.get('selectedTransport');

  return `
    <div class="screen-content">
      <div>
        ${renderBadge('LOGISTICS ON ONDC', 'primary')}
        <h2 class="headline-md mt-xs">Book Produce Transport</h2>
        <p class="caption text-secondary">
          Aggregated commercial vehicles with verified drivers, GPS transit tracking & digital transit pass.
        </p>
      </div>

      <!-- Route Overview Card -->
      ${renderCard({
        content: `
          <div class="route-summary-box">
            <div class="text-xl">🛣️</div>
            <div class="flex-1">
              <div class="route-arrow-endpoints">
                <span>Khargone Farm Gate</span>
                <span>→</span>
                <span>Indore ITC Hub (70 km)</span>
              </div>
              <div class="caption text-muted mt-2xs">
                Load: 100 Quintals (10 MT) · Wheat Sharbati
              </div>
            </div>
          </div>
        `
      })}

      <!-- Cost Responsibility Split Toggle -->
      ${renderCard({
        content: `
          <span class="label-md mb-xs block">Freight Responsibility</span>
          <div class="split-toggle-row">
            ${renderButton({ text: 'Buyer 100%', variant: 'primary', size: 'sm', extraClasses: 'label-sm' })}
            ${renderButton({ text: '50-50 Split', variant: 'outline', size: 'sm', extraClasses: 'label-sm' })}
            ${renderButton({ text: 'Farmer 100%', variant: 'outline', size: 'sm', extraClasses: 'label-sm' })}
          </div>
        `
      })}

      <!-- Available Vehicles Grid -->
      <div class="flex-col gap-sm">
        <span class="label-md">Available ONDC Logistics Partners</span>

        ${transports.length === 0 ? renderEmptyState({
          icon: '🚚',
          title: 'No Transport Providers Available',
          message: 'No ONDC logistics bids found for this route currently. Check back or change freight terms.',
          ctaText: 'Refresh Search',
          action: 'render'
        }) : transports.map(t => `
          <div class="transport-card ${t.id === selected ? 'selected' : ''}" data-action="select-transport" data-transport-id="${t.id}">
            <div class="transport-top-row">
              <div class="vehicle-meta">
                <div class="vehicle-icon-box">🚛</div>
                <div>
                  <div class="vehicle-provider">${t.provider}</div>
                  <div class="caption text-muted">${t.vehicle} · ETA ${t.eta}</div>
                </div>
              </div>
              <div class="text-right">
                <div class="data-md text-success">₹${t.totalEstimate}</div>
                <div class="caption text-muted">₹${t.ratePerKm}/km</div>
              </div>
            </div>

            <div class="transport-bottom-row">
              <span class="text-gold">★ ${t.rating} rating</span>
              <span class="text-accent">✓ GPS Live Enabled</span>
            </div>
          </div>
        `).join('')}
      </div>

      <!-- CTA -->
      <div class="auth-action-footer">
        ${renderButton({
          text: 'Confirm Transport & Dispatch Vehicle 🚚',
          variant: 'primary',
          size: 'lg',
          isBlock: true,
          action: 'confirm-transport'
        })}
      </div>
    </div>
  `;
}
