/* =====================================================================
   MittiMandi Screen: Cold Storage & Post-Harvest Arbitrage
   Migrated onto shared component library (F1 Foundation)
   ===================================================================== */

import { store } from '../state.js';
import { renderBadge } from '../components/badge.js';
import { renderButton } from '../components/button.js';
import { renderCard } from '../components/card.js';
import { renderEmptyState } from '../components/states.js';

export function renderStorage() {
  const warehouses = store.get('warehouses') || [];

  return `
    <div class="screen-content">
      <div>
        ${renderBadge('POST-HARVEST ARBITRAGE', 'tertiary')}
        <h2 class="headline-md mt-xs">Cold Storage & Warehousing</h2>
        <p class="caption text-secondary">
          Store grain in WDRA-accredited warehouses to capture projected off-season price surge.
        </p>
      </div>

      <!-- Arbitrage Calculator Box -->
      ${renderCard({
        variant: 'gold-gradient',
        content: `
          <span class="label-md text-gold mb-xs block">
            Storage Profitability Calculator (100 Qtl)
          </span>
          <div class="grid-2-col gap-sm">
            <div>
              <span class="text-muted caption">Storage Cost (45 Days):</span>
              <div class="data-sm text-danger">-₹4,200 (₹28/mo)</div>
            </div>
            <div>
              <span class="text-muted caption">Expected Value Gain:</span>
              <div class="data-sm text-success">+₹32,000 (+₹320/Qtl)</div>
            </div>
          </div>

          <div class="flex-row justify-between items-center mt-sm pt-sm border-t">
            <span class="font-semibold body-md">Net Profit After Storage:</span>
            <span class="display-data text-success data-lg">+₹27,800</span>
          </div>
        `
      })}

      <!-- Warehouse Selection Cards -->
      <div class="flex-col gap-sm">
        <span class="label-md">Accredited Warehouses Nearby</span>

        ${warehouses.length === 0 ? renderEmptyState({
          icon: '🏢',
          title: 'No Warehouses Found',
          message: 'No WDRA cold storage facilities found in your current cluster radius.',
          ctaText: 'Expand Radius',
          action: 'toast'
        }) : warehouses.map(w => renderCard({
          variant: 'interactive',
          action: 'toast',
          content: `
            <div class="flex-row justify-between items-start">
              <div>
                <span class="headline-sm">${w.name}</span>
                <div class="caption text-muted mt-2xs">
                  📍 ${w.distance} away · Space available: <strong>${w.capacityLeft}</strong>
                </div>
              </div>
              ${renderBadge('WDRA CERTIFIED', 'success')}
            </div>

            <div class="flex-row justify-between items-center mt-md pt-sm border-t">
              <div class="data-sm text-accent">₹${w.monthlyRatePerQtl} / Quintal / Month</div>
              ${renderButton({ text: 'Reserve Bay', variant: 'outline', size: 'sm', action: 'toast', dataAttrs: `data-toast-msg="Selected warehouse: ${w.name}"` })}
            </div>
          `
        })).join('')}
      </div>

      <div class="auth-action-footer">
        ${renderButton({
          text: 'Book Storage & Issue e-NWR Receipt',
          variant: 'tertiary',
          size: 'lg',
          isBlock: true,
          action: 'toast',
          dataAttrs: 'data-toast-msg="Warehouse space reserved! Electronic Negotiable Warehouse Receipt (e-NWR) generated."'
        })}
      </div>
    </div>
  `;
}
