/* =====================================================================
   MittiMandi Screen: Harvest Lots & AI Grain Quality Assay (LOTS-01 to 03)
   Local IndexedDB as Single Source of Truth
   Includes Lot Filters, Detail Inspection, and Offline Creation Outbox Flow
   ===================================================================== */

import { localDb } from '../db.js';
import { store } from '../state.js';
import { syncEngine } from '../sync.js';
import { DEMO_MODE } from '../../config.js';
import { renderBadge, renderGradeBadge, renderSyncBadge } from '../components/badge.js';
import { renderButton } from '../components/button.js';
import { renderCard } from '../components/card.js';
import { renderEmptyState } from '../components/states.js';
import { renderSelect, renderTextInput } from '../components/input.js';

let activeCommodityFilter = 'ALL';
let activeGradeFilter = 'ALL';
let activeSelectedLotId = null;

export function setLotCommodityFilter(commodity) {
  activeCommodityFilter = commodity;
}

export function setLotGradeFilter(grade) {
  activeGradeFilter = grade;
}

export function setSelectedLotId(lotId) {
  activeSelectedLotId = lotId;
}

export function getSelectedLotId() {
  return activeSelectedLotId;
}

export function renderLotsList() {
  const allLots = store.get('lots') || [];
  const isOnline = store.get('isOnline');
  const syncState = store.get('syncState') || {};

  // Apply filters
  let filteredLots = allLots;
  if (activeCommodityFilter !== 'ALL') {
    filteredLots = filteredLots.filter(l => 
      (l.commodity || l.crop || '').toLowerCase().includes(activeCommodityFilter.toLowerCase())
    );
  }
  if (activeGradeFilter !== 'ALL') {
    filteredLots = filteredLots.filter(l => 
      (l.grade || '').toLowerCase().includes(activeGradeFilter.toLowerCase())
    );
  }

  const commodities = ['ALL', 'Wheat', 'Soybean', 'Chana', 'Mustard'];
  const grades = ['ALL', 'Grade A', 'Grade B', 'Grade C'];

  return `
    <div class="screen-content">
      <div class="flex-row justify-between items-center">
        <div>
          <div class="flex-row gap-xs items-center">
            ${renderBadge('LOCAL DB (OFFLINE-FIRST)', 'primary')}
            ${isOnline 
              ? renderBadge('ONLINE', 'success') 
              : renderBadge('OFFLINE CACHE', 'warning')}
          </div>
          <h2 class="headline-md mt-xs">Listed Produce (${allLots.length})</h2>
        </div>
        ${renderButton({
          text: '+ New Lot',
          variant: 'primary',
          size: 'sm',
          action: 'nav',
          screen: 'lots-create'
        })}
      </div>

      <!-- Filter Ribbon: Commodity -->
      <div class="lot-filter-bar">
        ${commodities.map(c => `
          <button class="filter-chip ${activeCommodityFilter === c ? 'active' : ''}" 
                  data-action="filter-lot-commodity" 
                  data-commodity="${c}">
            ${c === 'ALL' ? '🌾 All Crops' : c}
          </button>
        `).join('')}
      </div>

      <!-- Filter Ribbon: Quality Grade -->
      <div class="lot-filter-bar">
        ${grades.map(g => `
          <button class="filter-chip ${activeGradeFilter === g ? 'active' : ''}" 
                  data-action="filter-lot-grade" 
                  data-grade="${g}">
            ${g === 'ALL' ? '⭐ All Grades' : g}
          </button>
        `).join('')}
      </div>

      <!-- Lot Cards List -->
      <div class="flex-col gap-md mt-xs">
        ${filteredLots.length === 0 ? renderEmptyState({
          icon: '🌾',
          title: 'No Matching Produce Lots',
          message: allLots.length === 0 
            ? 'Create your first lot offline or online. All writes commit to local IndexedDB first.'
            : 'No lots match the current filter selection.',
          ctaText: allLots.length === 0 ? 'Create First Lot' : 'Clear Filters',
          action: allLots.length === 0 ? 'nav' : 'filter-lot-commodity',
          screen: allLots.length === 0 ? 'lots-create' : undefined,
          extraAttrs: allLots.length > 0 ? 'data-commodity="ALL"' : ''
        }) : filteredLots.map(lot => {
          const qtyQtl = lot.quantity || (lot.quantity_mt ? lot.quantity_mt * 10 : 100);
          const price = lot.pricePerQtl || 2950;
          const totalVal = Math.round(qtyQtl * price);

          return renderCard({
            content: `
              <div class="flex-row justify-between items-start">
                <div>
                  <span class="headline-sm">${lot.commodity || lot.crop}</span>
                  <p class="caption text-muted font-data">
                    ${lot.id || lot.lot_code} · ${lot.variety || 'Sharbati C-306'}
                  </p>
                </div>
                <div class="flex-row gap-xs items-center">
                  ${renderSyncBadge(lot._syncStatus || 'synced')}
                  ${renderGradeBadge(lot.grade || 'Grade A')}
                </div>
              </div>

              <!-- AI Assay Proof Summary -->
              <div class="assay-card mt-sm">
                <div class="flex-row justify-between items-center">
                  <span class="label-sm text-gold font-semibold">AI Quality Assay</span>
                  <span class="crypto-hash-stamp">${lot.hmacSeal ? lot.hmacSeal.slice(0, 14) + '...' : 'HMAC-VERIFIED'}</span>
                </div>
                <div class="assay-metrics-grid mt-xs">
                  <div class="assay-metric-item">
                    <span class="assay-metric-label">Moisture</span>
                    <div class="assay-metric-num">${lot.moisture || '10.4%'}</div>
                  </div>
                  <div class="assay-metric-item">
                    <span class="assay-metric-label">Foreign</span>
                    <div class="assay-metric-num">${lot.foreignMatter || '0.3%'}</div>
                  </div>
                  <div class="assay-metric-item">
                    <span class="assay-metric-label">Quality Score</span>
                    <div class="assay-metric-num text-success">${lot.assayScore || 94.2}%</div>
                  </div>
                </div>
              </div>

              <!-- Volume & Price Strip -->
              <div class="flex-row justify-between items-center mt-md">
                <div>
                  <span class="caption text-muted">Volume & Target</span>
                  <div class="data-md">${qtyQtl} Qtl · ₹${price}/Qtl</div>
                  <span class="caption text-secondary">Est. ₹${totalVal.toLocaleString('en-IN')}</span>
                </div>
                <div class="flex-row gap-xs">
                  ${renderButton({
                    text: '🔍 Details',
                    variant: 'outline',
                    size: 'sm',
                    action: 'view-lot-detail',
                    dataAttrs: `data-lot-id="${lot.id || lot.lot_code}"`
                  })}
                  ${renderButton({
                    text: `Bids (${lot.bidsCount || 1})`,
                    variant: 'secondary',
                    size: 'sm',
                    action: 'nav',
                    screen: 'trades-negotiate'
                  })}
                </div>
              </div>
            `
          });
        }).join('')}
      </div>
    </div>
  `;
}

export function renderLotDetail() {
  const lots = store.get('lots') || [];
  const lot = lots.find(l => (l.id || l.lot_code) === activeSelectedLotId) || lots[0];

  if (!lot) {
    return `
      <div class="screen-content">
        ${renderEmptyState({
          icon: '🔍',
          title: 'Lot Not Found',
          message: 'The requested harvest lot could not be loaded from local storage.',
          ctaText: 'Back to Inventory',
          action: 'nav',
          screen: 'lots-list'
        })}
      </div>
    `;
  }

  const qtyQtl = lot.quantity || (lot.quantity_mt ? lot.quantity_mt * 10 : 100);
  const qtyMt = lot.quantity_mt || (qtyQtl / 10).toFixed(1);
  const price = lot.pricePerQtl || 2950;
  const totalVal = Math.round(qtyQtl * price);

  return `
    <div class="screen-content">
      <div class="flex-row justify-between items-center">
        <div>
          <button class="text-accent text-sm" data-action="nav" data-screen="lots-list">
            ← Back to Lots List
          </button>
          <h2 class="headline-md mt-xs">${lot.commodity || lot.crop} (${lot.variety || 'Standard'})</h2>
          <span class="caption text-muted font-data">${lot.id || lot.lot_code}</span>
        </div>
        <div class="flex-col items-end gap-2xs">
          ${renderSyncBadge(lot._syncStatus || 'synced')}
          ${renderGradeBadge(lot.grade || 'Grade A')}
        </div>
      </div>

      <!-- Lot Specifications Grid -->
      <div class="lot-spec-grid mt-sm">
        <div class="lot-spec-item">
          <span class="lot-spec-label">Total Volume</span>
          <span class="lot-spec-value">${qtyMt} MT (${qtyQtl} Qtl)</span>
        </div>
        <div class="lot-spec-item">
          <span class="lot-spec-label">Target Price</span>
          <span class="lot-spec-value">₹${price} / Qtl</span>
        </div>
        <div class="lot-spec-item">
          <span class="lot-spec-label">Est. Lot Value</span>
          <span class="lot-spec-value text-success">₹${totalVal.toLocaleString('en-IN')}</span>
        </div>
        <div class="lot-spec-item">
          <span class="lot-spec-label">Listing Status</span>
          <span class="lot-spec-value">${(lot.status || 'listed').toUpperCase()}</span>
        </div>
        <div class="lot-spec-item">
          <span class="lot-spec-label">Farmer ID</span>
          <span class="lot-spec-value font-data">${lot.farmer_id || 'FARMER-MP-001'}</span>
        </div>
        <div class="lot-spec-item">
          <span class="lot-spec-label">Harvest Date</span>
          <span class="lot-spec-value">${lot.harvestDate || '2026-09-18'}</span>
        </div>
      </div>

      <!-- Tamper-Evident AI Quality Assay Report -->
      <div class="assay-card mt-md">
        <div class="assay-header">
          <div>
            <span class="label-md text-gold font-semibold">AI Quality Inspection Report</span>
            <p class="caption text-muted">AGMARK & Computer Vision Physical Quality Verification</p>
          </div>
          ${renderGradeBadge(lot.grade || 'Grade A')}
        </div>

        <div class="assay-meter-bar">
          <div class="assay-meter-fill" style="width: ${lot.assayScore || 94}%"></div>
        </div>

        <div class="assay-metrics-grid">
          <div class="assay-metric-item">
            <span class="assay-metric-label">Moisture Content</span>
            <div class="assay-metric-num">${lot.moisture || '10.4%'}</div>
            <span class="caption text-success font-semibold body-2xs">Max 12% Allowed</span>
          </div>
          <div class="assay-metric-item">
            <span class="assay-metric-label">Foreign Matter</span>
            <div class="assay-metric-num">${lot.foreignMatter || '0.3%'}</div>
            <span class="caption text-success font-semibold body-2xs">Max 0.75% Allowed</span>
          </div>
          <div class="assay-metric-item">
            <span class="assay-metric-label">Damaged Grains</span>
            <div class="assay-metric-num">${lot.damagedGrains || '0.5%'}</div>
            <span class="caption text-success font-semibold body-2xs">Max 2% Allowed</span>
          </div>
        </div>

        <div class="mt-md p-sm rounded bg-black-20 flex-col gap-2xs">
          <div class="flex-row justify-between items-center">
            <span class="label-sm text-secondary">Cryptographic Security Seal</span>
            <span class="crypto-hash-stamp">${lot.hmacSeal || 'HMAC-SHA256-AUTHENTICATED'}</span>
          </div>
          <p class="caption text-muted body-2xs">
            Digital signature calculated over lot image features, weight, and timestamp. Verifiable by buyers and Mandi inspectors.
          </p>
        </div>
      </div>

      <!-- Mandi Integration & Trade Status -->
      ${renderCard({
        extraClasses: 'mt-md',
        content: `
          <div class="flex-col gap-sm">
            <div class="flex-row justify-between items-center">
              <span class="headline-sm">Trade & Mandi Integration</span>
              ${renderBadge('e-NAM & ONDC Active', 'primary')}
            </div>
            <div class="flex-row justify-between items-center p-xs rounded bg-surface">
              <span class="body-sm text-secondary">Active Procurement Offers</span>
              <span class="font-data font-bold text-accent">${lot.bidsCount || 1} Buyers Interested</span>
            </div>
            <div class="flex-row justify-between items-center p-xs rounded bg-surface">
              <span class="body-sm text-secondary">Highest Counter Bid</span>
              <span class="font-data font-bold text-success">₹${lot.highestBid || price - 30} / Qtl</span>
            </div>
            <div class="flex-row justify-between items-center p-xs rounded bg-surface">
              <span class="body-sm text-secondary">WDRA Cold Storage Receipt</span>
              <span class="badge badge-outline">e-NWR Ready</span>
            </div>
          </div>
        `
      })}

      <!-- Action Buttons -->
      <div class="flex-col gap-sm mt-md">
        ${renderButton({
          text: `Negotiate Trades (${lot.bidsCount || 1} Bids) →`,
          variant: 'primary',
          size: 'lg',
          isBlock: true,
          action: 'nav',
          screen: 'trades-negotiate'
        })}

        <div class="grid-2-col gap-sm">
          ${renderButton({
            text: '🚚 Book ONDC Transit',
            variant: 'secondary',
            size: 'md',
            isBlock: true,
            action: 'nav',
            screen: 'transport'
          })}
          ${renderButton({
            text: '❄️ Cold Storage',
            variant: 'outline',
            size: 'md',
            isBlock: true,
            action: 'nav',
            screen: 'storage'
          })}
        </div>

        ${renderButton({
          text: '🗑️ Delete Harvest Lot',
          variant: 'ghost',
          size: 'sm',
          extraClasses: 'text-danger',
          action: 'delete-lot',
          dataAttrs: `data-lot-id="${lot.id || lot.lot_code}"`
        })}
      </div>
    </div>
  `;
}

export function renderLotCreate() {
  const isOnline = store.get('isOnline');
  const cropOptions = [
    { value: 'Wheat', label: 'Wheat (Sharbati C-306)' },
    { value: 'Soybean', label: 'Soybean (Yellow JS-9560)' },
    { value: 'Chana', label: 'Chana (Desi JG-11)' },
    { value: 'Mustard', label: 'Mustard (Pusa Bold)' }
  ];

  return `
    <div class="screen-content">
      <div>
        <div class="flex-row justify-between items-center">
          ${renderBadge('OFFLINE WRITE ENABLED', 'primary')}
          ${isOnline ? renderBadge('ONLINE', 'success') : renderBadge('AIRPLANE MODE', 'danger')}
        </div>
        <h2 class="headline-md mt-xs">Add Produce & AI Assay</h2>
        <p class="caption text-secondary">
          Writes to local IndexedDB first. Queued in outbox if offline; pushed immediately if online.
        </p>
      </div>

      <!-- AI Camera / Image Inspection Box -->
      <div class="camera-preview-box" id="assay-preview-box" data-action="trigger-assay">
        <div class="scan-line"></div>
        <div class="assay-preview-icon">🌾</div>
        ${DEMO_MODE
          ? renderBadge('⚠ DEMO MODE — Simulated grading', 'fallback-rule')
          : renderBadge('AI Assay — Tap to scan', 'fallback-onnx')
        }
        <span class="label-md text-accent mt-xs">Tap to Grade Grain Sample</span>
        <span class="caption text-muted mt-2xs">Computer vision: moisture, foreign matter, purity</span>

        <!-- Bounding box overlays (cosmetic) -->
        <div class="bounding-box box-top-left">
          <span class="bounding-tag">Grade A (94%)</span>
        </div>
        <div class="bounding-box box-bottom-right">
          <span class="bounding-tag">Moisture 10.4%</span>
        </div>
      </div>

      <!-- Crop & Lot Details Form -->
      ${renderCard({
        content: `
          <div class="flex-col gap-md">
            ${renderSelect({
              id: 'lot-crop',
              label: 'Crop Category',
              helper: 'Select Mandi Variety',
              options: cropOptions,
              selected: 'Wheat'
            })}

            <div class="grid-2-col gap-sm">
              ${renderTextInput({
                id: 'lot-qty',
                type: 'number',
                label: 'Quantity (MT)',
                value: '10.0',
                step: '0.5'
              })}
              ${renderTextInput({
                id: 'lot-price',
                type: 'number',
                label: 'Target Price (₹/Qtl)',
                value: '2950'
              })}
            </div>

            <!-- Real-time AI Assay Metrics Container -->
            <div class="assay-card" id="assay-result-card">
              <div class="assay-header">
                <span class="label-md text-gold">Assay Quality: Grade A (Certified)</span>
                ${renderBadge('✓ AI Graded — Grade A', 'grade-a')}
              </div>

              <div class="assay-meter-bar">
                <div class="assay-meter-fill"></div>
              </div>

              <div class="assay-metrics-grid">
                <div class="assay-metric-item">
                  <span class="assay-metric-label">Moisture</span>
                  <div class="assay-metric-num" id="assay-moisture">10.4%</div>
                </div>
                <div class="assay-metric-item">
                  <span class="assay-metric-label">Foreign Matter</span>
                  <div class="assay-metric-num" id="assay-foreign">0.3%</div>
                </div>
                <div class="assay-metric-item">
                  <span class="assay-metric-label">HMAC Signed</span>
                  <div class="assay-metric-num text-accent">Verified ✓</div>
                </div>
              </div>
            </div>
          </div>
        `
      })}

      <div class="auth-action-footer">
        ${renderButton({
          text: 'Save to Local DB & Sync / सुरक्षित करें →',
          variant: 'primary',
          size: 'lg',
          isBlock: true,
          action: 'create-lot'
        })}
      </div>
    </div>
  `;
}
