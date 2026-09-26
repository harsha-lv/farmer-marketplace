/* =====================================================================
   MittiMandi Screen: Escrow Milestones & e-NWR Warehouse Receipt Pledge Finance (FIN-01 to 02)
   Instant UPI Payouts, Escrow Milestones & Concessional Agri Loans
   ===================================================================== */

import { store } from '../state.js';
import { api } from '../api.js';
import { renderBadge } from '../components/badge.js';
import { renderButton } from '../components/button.js';
import { renderCard } from '../components/card.js';
import { renderTextInput, renderSelect } from '../components/input.js';
import { renderEmptyState } from '../components/states.js';

let activeEligibility = null;
let activeLoansList = [
  {
    loan_id: 'LOAN-ENWR-2026-088',
    lot_code: 'LOT-IND-2026-081',
    commodity: 'Wheat (Sharbati)',
    sanctioned_amount_inr: 221250,
    disbursement_mode: 'BANK_TRANSFER',
    interest_rate: '7.25% p.a.',
    tenure_days: 90,
    status: 'ACTIVE',
    disbursed_at: '2026-09-20T10:00:00Z',
    lender: 'State Bank of India (Agri Division)'
  }
];

export function setPledgeEligibility(res) {
  activeEligibility = res;
}

export function addPledgeLoan(loan) {
  activeLoansList.unshift(loan);
}

export function getPledgeLoansList() {
  return activeLoansList;
}

export function renderFinance() {
  const neg = store.get('negotiation');
  const amount = neg ? neg.currentOffer * neg.quantityLock : 292000;
  const loans = getPledgeLoansList();

  return `
    <div class="screen-content">
      <div>
        <div class="flex-row gap-xs items-center">
          ${renderBadge('ESCROW & e-NWR FINANCE', 'success')}
          ${renderBadge('WDRA ACCREDITED', 'primary')}
        </div>
        <h2 class="headline-md mt-xs">Payments & Pledge Credit</h2>
        <p class="caption text-secondary">
          Automated milestone escrow settlements and instantaneous post-harvest loans against e-NWR receipts.
        </p>
      </div>

      <!-- Settlement Status Header Card -->
      ${renderCard({
        variant: 'primary-gradient',
        extraClasses: 'text-center',
        content: `
          <span class="caption text-muted">Cleared Payout Deposited to Bank</span>
          <div class="display-data text-success payout-amount">
            ₹${amount.toLocaleString()}
          </div>
          <div class="flex-row justify-center gap-sm mt-xs">
            ${renderBadge('UPI: ramesh.patel@okhdfcbank', 'primary')}
            ${renderBadge('UTR: 26092049182', 'success')}
          </div>
        `
      })}

      <!-- Escrow Milestone Pipeline -->
      ${renderCard({
        content: `
          <div class="flex-row justify-between items-center mb-md">
            <span class="label-md font-semibold text-primary">Automated Escrow Milestones</span>
            ${renderBadge('100% FUNDED', 'success')}
          </div>

          <div class="milestone-list">
            <!-- Milestone 1 -->
            <div class="milestone-item">
              <div class="milestone-badge completed">✓</div>
              <div class="flex-1">
                <div class="milestone-title">1. Buyer Escrow Funded (100%)</div>
                <div class="caption text-muted">₹${amount.toLocaleString()} locked in ICICI Partner Escrow</div>
              </div>
            </div>
            <!-- Milestone 2 -->
            <div class="milestone-item">
              <div class="milestone-badge completed">✓</div>
              <div class="flex-1">
                <div class="milestone-title">2. Farm Gate Dispatch & Weighment</div>
                <div class="caption text-muted">100 Quintals verified via ONDC Logistics TruckSe</div>
              </div>
            </div>
            <!-- Milestone 3 -->
            <div class="milestone-item">
              <div class="milestone-badge completed">✓</div>
              <div class="flex-1">
                <div class="milestone-title">3. AI Quality Match at Warehouse Gate</div>
                <div class="caption text-muted">Moisture 10.4% verified (Grade A re-confirmed)</div>
              </div>
            </div>
            <!-- Milestone 4 -->
            <div class="milestone-item">
              <div class="milestone-badge active">★</div>
              <div class="flex-1">
                <div class="milestone-title text-accent">4. Instant UPI / Bank Release</div>
                <div class="caption text-secondary">Direct settlement without mandi middleman deductions</div>
              </div>
            </div>
          </div>
        `
      })}

      <!-- e-NWR Warehouse Receipt Pledge Loan Section -->
      ${renderCard({
        content: `
          <div class="flex-row justify-between items-center mb-sm">
            <div>
              <span class="label-md font-semibold text-gold block">e-NWR Post-Harvest Pledge Loan</span>
              <span class="caption text-muted">Avoid distress sale: get 75% loan against stored produce @ 7.25% p.a.</span>
            </div>
            ${renderBadge('75% LTV', 'tertiary')}
          </div>

          <div class="flex-col gap-sm">
            <div class="grid-2-col gap-sm">
              ${renderTextInput({
                id: 'pledge-lot-code',
                label: 'Stored Lot Code',
                placeholder: 'e.g. LOT-IND-2026-081',
                value: 'LOT-IND-2026-081'
              })}
              ${renderTextInput({
                id: 'pledge-amount',
                type: 'number',
                label: 'Loan Amount (₹)',
                placeholder: 'e.g. 200000',
                value: '221250'
              })}
            </div>

            <div class="grid-2-col gap-sm">
              ${renderSelect({
                id: 'pledge-tenure',
                label: 'Loan Tenure',
                options: [
                  { value: '30', label: '30 Days (Short Term)' },
                  { value: '90', label: '90 Days (Quarterly)' },
                  { value: '180', label: '180 Days (Half-Yearly)' }
                ],
                selected: '90'
              })}
              ${renderSelect({
                id: 'pledge-disburse-mode',
                label: 'Disbursement Mode',
                options: [
                  { value: 'BANK_TRANSFER', label: 'Direct Bank Transfer (IMPS)' },
                  { value: 'ERUPI_VOUCHER', label: 'e-RUPI Digital Agri Voucher' }
                ],
                selected: 'BANK_TRANSFER'
              })}
            </div>

            <div class="flex-row justify-between items-center mt-xs">
              <button class="btn btn-outline btn-sm text-accent" data-action="check-pledge-eligibility">
                🔍 Check Max LTV Eligibility
              </button>
              ${renderButton({
                text: 'Apply for Pledge Loan →',
                variant: 'primary',
                size: 'md',
                action: 'apply-pledge-loan'
              })}
            </div>

            ${activeEligibility ? `
              <div class="p-sm rounded bg-black-20 flex-col gap-2xs mt-xs body-xs">
                <div class="flex-row justify-between">
                  <span class="text-secondary">Assessed Lot Valuation:</span>
                  <strong class="font-data text-primary">₹${activeEligibility.commodity_valuation_inr.toLocaleString()}</strong>
                </div>
                <div class="flex-row justify-between">
                  <span class="text-secondary">Maximum Sanction (75% LTV):</span>
                  <strong class="font-data text-success">₹${activeEligibility.max_loan_amount_inr.toLocaleString()}</strong>
                </div>
                <div class="flex-row justify-between">
                  <span class="text-secondary">Concessional Agri Interest:</span>
                  <span class="text-gold font-bold">7.25% p.a. (NABARD Refinanced)</span>
                </div>
              </div>
            ` : ''}
          </div>
        `
      })}

      <!-- Active Pledge Loans Ledger -->
      <div class="flex-col gap-sm mt-md">
        <span class="label-md font-semibold">Active e-NWR Loans (${loans.length})</span>

        ${loans.map(loan => `
          <div class="transport-card">
            <div class="flex-row justify-between items-start">
              <div>
                <span class="headline-sm font-data">₹${loan.sanctioned_amount_inr.toLocaleString()}</span>
                <p class="caption text-muted font-data">${loan.loan_id} · ${loan.lot_code}</p>
              </div>
              ${renderBadge(loan.status, 'success')}
            </div>

            <div class="lot-spec-grid mt-xs body-xs">
              <div class="lot-spec-item">
                <span class="lot-spec-label">Lender</span>
                <span class="lot-spec-value">${loan.lender || 'SBI Agri'}</span>
              </div>
              <div class="lot-spec-item">
                <span class="lot-spec-label">Tenure</span>
                <span class="lot-spec-value">${loan.tenure_days} Days</span>
              </div>
              <div class="lot-spec-item">
                <span class="lot-spec-label">Rate</span>
                <span class="lot-spec-value text-accent">${loan.interest_rate || '7.25%'}</span>
              </div>
              <div class="lot-spec-item">
                <span class="lot-spec-label">Disbursement</span>
                <span class="lot-spec-value">${loan.disbursement_mode}</span>
              </div>
            </div>
          </div>
        `).join('')}
      </div>
    </div>
  `;
}
