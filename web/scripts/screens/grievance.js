/* =====================================================================
   MittiMandi Screen: ONDC Issue & Grievance Management (IGM v2.0)
   Farmer Dispute Resolution for Quality, Logistics, and Escrow Settlements
   ===================================================================== */

import { store } from '../state.js';
import { api } from '../api.js';
import { renderBadge } from '../components/badge.js';
import { renderButton } from '../components/button.js';
import { renderCard } from '../components/card.js';
import { renderTextInput, renderSelect, renderFormGroup } from '../components/input.js';
import { renderEmptyState } from '../components/states.js';

const DEFAULT_GRIEVANCES = [
  {
    ticket_id: 'IGM-2026-901',
    transaction_id: 'TXN-ITC-2026-081',
    category: 'QUALITY',
    sub_category: 'MOISTURE_DISPUTE',
    description: 'Buyer reported moisture 11.8% at gate, while AI initial assay verified 10.4%. Requesting third-party lab umpire re-assay.',
    status: 'ESCALATED',
    sla_hours_remaining: 18,
    created_at: '2026-09-24T11:00:00Z',
    respondent: 'ITC Agri Business Ltd.'
  },
  {
    ticket_id: 'IGM-2026-902',
    transaction_id: 'TXN-LSP-2026-044',
    category: 'LOGISTICS',
    sub_category: 'TRANSIT_DELAY',
    description: 'TruckSe 14ft Eicher vehicle delayed by 4 hours exceeding ONDC logistics SLA agreement.',
    status: 'RESOLVED',
    sla_hours_remaining: 0,
    created_at: '2026-09-22T08:30:00Z',
    respondent: 'TruckSe Logistics (ONDC)'
  }
];

export function getGrievancesList() {
  const custom = store.get('grievances') || [];
  return custom.length > 0 ? custom : DEFAULT_GRIEVANCES;
}

export function renderGrievance() {
  const grievances = getGrievancesList();

  const categories = [
    { value: 'QUALITY', label: '🌾 Produce Quality & Grade Mismatch' },
    { value: 'LOGISTICS', label: '🚚 Logistics Delay / Route Deviation' },
    { value: 'PAYMENT', label: '💰 Escrow Payout Delay / Deduction' },
    { value: 'WEIGHMENT', label: '⚖️ Farm Gate vs Mill Weighment Discrepancy' }
  ];

  return `
    <div class="screen-content">
      <div class="flex-row justify-between items-center">
        <div>
          ${renderBadge('ONDC IGM v2.0 RESOLUTION', 'primary')}
          <h2 class="headline-md mt-xs">Grievance & Claims Desk</h2>
          <p class="caption text-secondary">
            File dispute tickets protected under ONDC protocol SLA. Automated escalation to Ombudsman within 24 hours.
          </p>
        </div>
      </div>

      <!-- File New Grievance Card -->
      ${renderCard({
        content: `
          <span class="label-md font-semibold text-primary mb-sm block">Raise New IGM Dispute Ticket</span>

          <div class="flex-col gap-sm">
            ${renderSelect({
              id: 'igm-category',
              label: 'Dispute Category',
              options: categories,
              selected: 'QUALITY'
            })}

            <div class="grid-2-col gap-sm">
              ${renderTextInput({
                id: 'igm-txn-id',
                label: 'Transaction / Order ID',
                placeholder: 'e.g. TXN-ITC-2026-081',
                value: 'TXN-ITC-2026-081'
              })}
              ${renderTextInput({
                id: 'igm-lot-code',
                label: 'Lot Reference Code',
                placeholder: 'e.g. LOT-IND-2026-081',
                value: 'LOT-IND-2026-081'
              })}
            </div>

            <div class="form-group">
              <label for="igm-desc" class="form-label">Dispute Details & Evidence Statement</label>
              <textarea id="igm-desc" 
                        class="form-input text-sm" 
                        rows="3" 
                        placeholder="Provide details of the discrepancy (e.g. weighment difference, unauthorized deduction, assay re-check request)...">Grade A grain sample delivered within certified moisture parameters; buyer requested unjustified ₹30/qtl deduction.</textarea>
            </div>

            <div class="flex-row justify-end mt-xs">
              ${renderButton({
                text: 'Submit IGM Ticket →',
                variant: 'primary',
                size: 'md',
                action: 'submit-grievance'
              })}
            </div>
          </div>
        `
      })}

      <!-- Active Tickets List -->
      <div class="flex-col gap-md mt-md">
        <div class="flex-row justify-between items-center">
          <span class="label-md font-semibold">Active & Historic Tickets (${grievances.length})</span>
          <span class="caption text-muted">Auto-escalated if unresolved</span>
        </div>

        ${grievances.map(g => {
          const isResolved = g.status === 'RESOLVED';
          const isEscalated = g.status === 'ESCALATED';
          let badgeVariant = 'primary';
          if (isResolved) badgeVariant = 'success';
          if (isEscalated) badgeVariant = 'danger';

          return renderCard({
            content: `
              <div class="flex-row justify-between items-start">
                <div>
                  <div class="flex-row gap-xs items-center">
                    <span class="headline-sm">${g.ticket_id}</span>
                    ${renderBadge(g.status, badgeVariant)}
                  </div>
                  <span class="caption text-muted font-data">${g.transaction_id} · ${g.category}</span>
                </div>
                ${!isResolved ? `
                  <span class="caption text-warning font-semibold">⏱️ SLA: ${g.sla_hours_remaining}h</span>
                ` : `
                  <span class="caption text-success font-semibold">✓ Closed</span>
                `}
              </div>

              <p class="body-sm text-secondary mt-sm">
                ${g.description}
              </p>

              <div class="flex-row justify-between items-center mt-md pt-sm border-t">
                <span class="caption text-muted">Respondent: <strong>${g.respondent}</strong></span>
                ${!isResolved ? `
                  <button class="btn btn-outline btn-sm text-danger" 
                          data-action="escalate-grievance" 
                          data-ticket-id="${g.ticket_id}">
                    ⚡ Escalate to Ombudsman
                  </button>
                ` : `
                  <span class="caption text-muted body-2xs">Resolution Accepted</span>
                `}
              </div>
            `
          });
        }).join('')}
      </div>
    </div>
  `;
}
