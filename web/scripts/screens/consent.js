/* =====================================================================
   MittiMandi Screen: Consent & Data Rights (DPDP Act 2023 Compliance)
   Farmer Self-Service Consent Management, Revocation & Right to Erasure
   ===================================================================== */

import { store } from '../state.js';
import { api } from '../api.js';
import { renderBadge } from '../components/badge.js';
import { renderButton } from '../components/button.js';
import { renderCard } from '../components/card.js';
import { renderEmptyState, renderLoadingSkeleton } from '../components/states.js';
import { modalAlert, modalConfirm } from '../components/modal.js';

let erasureCert = null;
let auditTrailData = null;

// Initial client-side tracked consent artifacts
const DEFAULT_CONSENTS = [
  {
    artifact_id: 'CONSENT-AGRISTACK-2026-001',
    title: 'AgriStack Land Registry Sync',
    purpose: 'Verify farmland parcels, crop classification & PM-KISAN entitlement verification',
    attributes: ['land_records', 'khasra_number', 'geo_coordinates', 'crop_sown'],
    status: 'granted',
    created_at: '2026-09-01T10:00:00Z',
    expires_at: '2027-09-01T10:00:00Z',
    fiduciary: 'Department of Agriculture & Farmers Welfare (AgriStack)',
    signature: 'a1b2c3d4e5f67890123456789abcdef0123456789abcdef0123456789abcdef0'
  },
  {
    artifact_id: 'CONSENT-MANDI-KYC-2026-002',
    title: 'Mandi Trade Settlement & e-KYC',
    purpose: 'Direct bank transfer and settlement via Escrow on e-NAM and ONDC transactions',
    attributes: ['phone_number', 'bank_account_hash', 'pan_hash', 'aadhaar_vault_ref'],
    status: 'granted',
    created_at: '2026-09-10T14:30:00Z',
    expires_at: '2027-09-10T14:30:00Z',
    fiduciary: 'MittiMandi Trade Settlement Gateway',
    signature: 'b2c3d4e5f6a17890123456789abcdef0123456789abcdef0123456789abcdef1'
  },
  {
    artifact_id: 'CONSENT-ASSAY-AI-2026-003',
    title: 'Grain Quality Computer Vision & Assay Imagery',
    purpose: 'Computer vision grain sample scanning, foreign matter detection & AGMARK certification',
    attributes: ['grain_photographs', 'sample_assay_metrics', 'moisture_readings'],
    status: 'granted',
    created_at: '2026-09-15T09:15:00Z',
    expires_at: '2027-09-15T09:15:00Z',
    fiduciary: 'MittiMandi Agri-Vision Neural Lab',
    signature: 'c3d4e5f6a1b27890123456789abcdef0123456789abcdef0123456789abcdef2'
  },
  {
    artifact_id: 'CONSENT-ONDC-TRANSIT-2026-004',
    title: 'Logistics Fleet Dispatch Geolocation',
    purpose: 'Share farm gate pick-up coordinates with verified ONDC freight logistics providers',
    attributes: ['farm_gate_gps', 'dispatch_schedule', 'cargo_weight_tonnes'],
    status: 'granted',
    created_at: '2026-09-20T16:45:00Z',
    expires_at: '2026-12-20T16:45:00Z',
    fiduciary: 'ONDC Logistics Unified Network',
    signature: 'd4e5f6a1b2c37890123456789abcdef0123456789abcdef0123456789abcdef3'
  }
];

export function getConsentsList() {
  const custom = store.get('consents') || [];
  return custom.length > 0 ? custom : DEFAULT_CONSENTS;
}

export function setErasureCert(cert) {
  erasureCert = cert;
}

export function setAuditTrailData(data) {
  auditTrailData = data;
}

export function renderConsent() {
  const consents = getConsentsList();

  return `
    <div class="screen-content">
      <div class="flex-row justify-between items-center">
        <div>
          ${renderBadge('DPDP ACT 2023 COMPLIANT', 'primary')}
          <h2 class="headline-md mt-xs">Consent & Data Privacy</h2>
          <p class="caption text-secondary">
            Section 6 & 12: You possess sovereign data principal rights to inspect, revoke, or purge your records.
          </p>
        </div>
        ${renderButton({
          text: '+ Grant Consent',
          variant: 'primary',
          size: 'sm',
          action: 'open-grant-consent-dialog'
        })}
      </div>

      <!-- Erasure Certificate Banner (if generated) -->
      ${erasureCert ? renderErasureCertCard(erasureCert) : ''}

      <!-- Audit Trail Banner (if viewed) -->
      ${auditTrailData ? renderAuditTrailCard(auditTrailData) : ''}

      <!-- Active Consent Artifacts List -->
      <div class="flex-col gap-md mt-sm">
        ${consents.map(c => renderConsentArtifactCard(c)).join('')}
      </div>

      <!-- DPDP Regulatory Information Card -->
      ${renderCard({
        extraClasses: 'mt-md bg-surface-elevated',
        content: `
          <div class="flex-row gap-sm items-start">
            <span class="body-lg">⚖️</span>
            <div class="flex-col gap-2xs">
              <span class="label-md font-semibold text-primary">Your Rights under DPDP Act 2023</span>
              <p class="caption text-muted">
                1. <strong>Right to Withdraw:</strong> Revoke consent instantly with digital signature proof.<br>
                2. <strong>Right to Erasure:</strong> Anonymize or permanently delete land parcels and harvest records.<br>
                3. <strong>Right to Grievance:</strong> Escalate violations to the Data Protection Board of India.
              </p>
            </div>
          </div>
        `
      })}
    </div>
  `;
}

function renderConsentArtifactCard(c) {
  const isGranted = c.status === 'granted';
  const isWithdrawn = c.status === 'withdrawn';
  const isPurged = c.status === 'purged';

  let statusBadge = renderBadge('✓ ACTIVE CONSENT', 'success');
  if (isWithdrawn) statusBadge = renderBadge('⚠ REVOKED / WITHDRAWN', 'warning');
  if (isPurged) statusBadge = renderBadge('🛡️ DATA PURGED (ANONYMIZED)', 'danger');

  return renderCard({
    content: `
      <div class="flex-row justify-between items-start">
        <div>
          <span class="headline-sm">${c.title}</span>
          <p class="caption text-muted font-data mt-2xs">
            ${c.artifact_id} · Exp: ${new Date(c.expires_at).toLocaleDateString()}
          </p>
        </div>
        ${statusBadge}
      </div>

      <div class="mt-sm">
        <span class="caption text-secondary"><strong>Purpose:</strong> ${c.purpose}</span>
      </div>

      <div class="mt-xs">
        <span class="caption text-muted"><strong>Data Fiduciary:</strong> ${c.fiduciary || 'MittiMandi Network'}</span>
      </div>

      <!-- Attributes Strip -->
      <div class="flex-row gap-xs flex-wrap mt-sm">
        ${(c.attributes || []).map(a => `
          <span class="badge badge-outline body-2xs">🏷️ ${a}</span>
        `).join('')}
      </div>

      <!-- Cryptographic Proof Hash -->
      <div class="flex-row justify-between items-center mt-sm p-2xs rounded bg-black-20">
        <span class="label-2xs text-muted">SHA-256 Signature</span>
        <span class="crypto-hash-stamp">${c.signature ? c.signature.slice(0, 16) + '...' : 'SECURE-HMAC'}</span>
      </div>

      <!-- Action Buttons -->
      <div class="flex-row justify-between items-center mt-md pt-sm border-t">
        <button class="btn btn-ghost btn-sm text-accent" 
                data-action="view-consent-audit" 
                data-artifact-id="${c.artifact_id}">
          📜 Audit Trail
        </button>

        <div class="flex-row gap-xs">
          ${isGranted ? `
            <button class="btn btn-outline btn-sm text-warning" 
                    data-action="revoke-consent" 
                    data-artifact-id="${c.artifact_id}">
              Revoke Consent
            </button>
            <button class="btn btn-outline btn-sm text-danger" 
                    data-action="anonymize-consent" 
                    data-artifact-id="${c.artifact_id}">
              🛡️ Purge Data
            </button>
          ` : `
            <span class="caption text-muted italic">No active processing</span>
          `}
        </div>
      </div>
    `
  });
}

function renderErasureCertCard(cert) {
  return renderCard({
    extraClasses: 'border-danger bg-surface-elevated mb-md',
    content: `
      <div class="flex-row justify-between items-center">
        <div>
          <span class="label-md text-danger font-semibold">OFFICIAL ERASURE CERTIFICATE</span>
          <h3 class="headline-sm mt-2xs">Right to Erasure Executed (Sec 12 DPDP)</h3>
        </div>
        <button class="btn btn-ghost btn-sm" data-action="dismiss-erasure-cert">✕ Dismiss</button>
      </div>

      <div class="lot-spec-grid mt-sm">
        <div class="lot-spec-item">
          <span class="lot-spec-label">Certificate ID</span>
          <span class="lot-spec-value font-data text-accent">${cert.certificate_id}</span>
        </div>
        <div class="lot-spec-item">
          <span class="lot-spec-label">Status</span>
          <span class="lot-spec-value text-success">${cert.status.toUpperCase()}</span>
        </div>
        <div class="lot-spec-item">
          <span class="lot-spec-label">Parcels Purged</span>
          <span class="lot-spec-value">${cert.parcels_purged} Record(s)</span>
        </div>
        <div class="lot-spec-item">
          <span class="lot-spec-label">Cache Keys Evicted</span>
          <span class="lot-spec-value">${(cert.cache_keys_evicted || []).length} Keys</span>
        </div>
      </div>

      <div class="mt-sm p-sm rounded bg-black-20">
        <span class="label-2xs text-muted block mb-2xs">Tamper-Evident Verification Hash</span>
        <span class="crypto-hash-stamp text-success body-xs font-data">${cert.verification_hash}</span>
      </div>

      <p class="caption text-muted mt-xs">
        Reason: ${cert.reason}. All personal identifiable information associated with artifact 
        <strong>${cert.artifact_id}</strong> has been expunged from primary storage and cache.
      </p>
    `
  });
}

function renderAuditTrailCard(audit) {
  const events = audit?.events || audit?.history || [
    { event: 'CONSENT_GRANTED', timestamp: '2026-09-01T10:00:00Z', actor: 'FARMER_AUTH' },
    { event: 'ATTRIBUTE_ACCESSED', timestamp: '2026-09-12T11:20:00Z', actor: 'AGRISTACK_RESOLVER' },
    { event: 'REVOCATION_REQUESTED', timestamp: new Date().toISOString(), actor: 'FARMER_PORTAL' }
  ];

  return renderCard({
    extraClasses: 'border-primary bg-surface-elevated mb-md',
    content: `
      <div class="flex-row justify-between items-center">
        <div>
          <span class="label-md text-primary font-semibold">IMMUTABLE CONSENT AUDIT LOG</span>
          <h3 class="headline-sm mt-2xs">Artifact: ${audit.artifact_id || 'CONSENT-REF'}</h3>
        </div>
        <button class="btn btn-ghost btn-sm" data-action="dismiss-audit-trail">✕ Close</button>
      </div>

      <div class="flex-col gap-xs mt-sm">
        ${events.map(ev => `
          <div class="flex-row justify-between items-center p-xs rounded bg-surface body-xs">
            <div class="flex-col">
              <span class="font-data font-semibold text-accent">${ev.event || ev.action || 'ACCESS'}</span>
              <span class="caption text-muted">${ev.actor || 'SYSTEM'}</span>
            </div>
            <span class="font-data text-secondary">${new Date(ev.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
          </div>
        `).join('')}
      </div>
    `
  });
}
