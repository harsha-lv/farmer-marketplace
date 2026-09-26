/* =====================================================================
   MittiMandi Screen: Trade Negotiation, Price Lock & Digital Agreement
   Migrated onto shared component library (F1 Foundation)
   ===================================================================== */

import { store } from '../state.js';
import { renderBadge } from '../components/badge.js';
import { renderButton } from '../components/button.js';
import { renderCard } from '../components/card.js';
import { renderEmptyState } from '../components/states.js';

export function renderTrades() {
  const neg = store.get('negotiation');

  if (!neg) {
    return `
      <div class="screen-content">
        <div class="flex-row justify-between items-center">
          <div>
            ${renderBadge('BILATERAL TRADE DESK', 'secondary')}
            <h2 class="headline-md mt-xs">Live Negotiation</h2>
          </div>
        </div>
        ${renderEmptyState({
          icon: '🤝',
          title: 'No Active Negotiation',
          message: 'You do not have any open price negotiations or buyer bids at the moment.',
          ctaText: 'Browse Produce Lots',
          action: 'nav',
          screen: 'lots-list'
        })}
      </div>
    `;
  }

  return `
    <div class="screen-content">
      <div class="flex-row justify-between items-center">
        <div>
          ${renderBadge('BILATERAL TRADE DESK', 'secondary')}
          <h2 class="headline-md mt-xs">Live Negotiation</h2>
        </div>
        ${renderBadge('PRICE LOCK: ACTIVE', 'success')}
      </div>

      <!-- Lot Context Box -->
      ${renderCard({
        variant: 'primary-gradient',
        content: `
          <div class="flex-row justify-between items-center">
            <div>
              <span class="headline-sm">Wheat (Sharbati C-306)</span>
              <div class="caption text-accent font-data">
                ${neg.lotId} · 100 Quintals Locked
              </div>
            </div>
            <div class="text-right">
              <span class="caption text-muted">Counter Offer</span>
              <div class="data-lg text-success">₹${neg.currentOffer}/Qtl</div>
            </div>
          </div>
        `
      })}

      <!-- Negotiation Thread / Ladder -->
      <div class="offer-chat-ladder">
        ${neg.history.map(item => `
          <div class="negotiation-bubble ${item.sender}">
            <div class="bubble-meta">
              <span>${item.sender === 'buyer' ? '🏢 Buyer: ' + neg.buyerName : '🌾 Farmer (You)'}</span>
              <strong class="${item.sender === 'buyer' ? 'text-secondary' : 'text-accent'}">
                ₹${item.price} / Qtl
              </strong>
            </div>
            <p class="body-md text-primary mt-2xs">
              ${item.note}
            </p>
          </div>
        `).join('')}
      </div>

      <!-- Live Counter Offer Form -->
      ${renderCard({
        content: `
          <span class="label-md text-primary mb-sm block">
            Submit Revised Counter Offer
          </span>
          <div class="flex-row gap-sm">
            <div class="counter-input-wrap">
              <input type="number" id="counter-price-input" class="input-box" value="${neg.farmerTarget}" placeholder="Enter ₹/Qtl">
              <span class="counter-unit">₹/Qtl</span>
            </div>
            ${renderButton({
              text: 'Counter',
              variant: 'secondary',
              size: 'md',
              action: 'send-counter-offer'
            })}
          </div>
        `
      })}

      <!-- Agreement Actions CTA -->
      <div class="auth-action-footer">
        ${renderButton({
          text: `Accept ₹${neg.currentOffer} & Generate Agreement (₹${(neg.currentOffer * neg.quantityLock).toLocaleString()})`,
          variant: 'primary',
          size: 'lg',
          isBlock: true,
          action: 'nav',
          screen: 'agreement-cert'
        })}
        <div class="flex-row justify-between caption text-muted">
          <span>✓ 100% Escrow backed</span>
          <span>✓ ONDC e-Way Bill generated</span>
        </div>
      </div>
    </div>
  `;
}

export function renderAgreementCert() {
  const neg = store.get('negotiation');

  if (!neg) {
    return `
      <div class="screen-content">
        <div>
          ${renderBadge('LEGAL CONTRACT', 'tertiary')}
          <h2 class="headline-md mt-xs">Digital Trade Agreement</h2>
        </div>
        ${renderEmptyState({
          icon: '📜',
          title: 'No Active Agreement',
          message: 'No locked trade negotiation is ready to generate an agreement certificate.',
          ctaText: 'View Produce Lots',
          action: 'nav',
          screen: 'lots-list'
        })}
      </div>
    `;
  }

  const totalAmount = neg.currentOffer * neg.quantityLock;

  return `
    <div class="screen-content">
      <div>
        ${renderBadge('LEGAL CONTRACT', 'tertiary')}
        <h2 class="headline-md mt-xs">Digital Trade Agreement</h2>
        <p class="caption text-secondary">
          Cryptographically sealed bilateral agricultural purchase contract with DPDP Act 2023 consent stamp.
        </p>
      </div>

      <div class="agreement-cert">
        <div class="agreement-header">
          <h3 class="headline-sm text-gold">MittiMandi Contract #MM-AGR-2026-992</h3>
          <span class="caption text-muted">Generated on: 26-09-2026 03:30 IST</span>
        </div>

        <div class="agreement-parties">
          <div>
            <span class="text-muted">Farmer (Seller):</span>
            <div class="agreement-party-name">Ramesh Patel</div>
            <div class="caption">Nimar FPO Member</div>
          </div>
          <div>
            <span class="text-muted">Buyer (Procuring Entity):</span>
            <div class="agreement-party-name">ITC Agri Business Ltd.</div>
            <div class="caption">GSTIN: 23AAACI1234F1Z5</div>
          </div>
        </div>

        <div class="agreement-escrow-box">
          <div>
            <div class="caption text-muted">Total Locked Consideration</div>
            <div class="display-data escrow-amount">₹${totalAmount.toLocaleString()}</div>
          </div>
          ${renderBadge('ESCROW DEPOSITED', 'success')}
        </div>

        <div class="crypto-hash-stamp">
          SHA-256 HMAC PROOF: 0x9b5d27fe810c4a921d7820bbca341908d172e9a629bcae710207
        </div>

        <div class="agreement-footer-note">
          Payment will be instantly disbursed to Farmer UPI/Bank upon digital transit confirmation & AI re-assay at delivery.
        </div>
      </div>

      <div class="auth-action-footer">
        ${renderButton({
          text: 'Arrange Dispatch & Transport →',
          variant: 'primary',
          size: 'lg',
          isBlock: true,
          action: 'nav',
          screen: 'transport'
        })}
      </div>
    </div>
  `;
}
