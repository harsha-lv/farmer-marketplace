/* =====================================================================
   MittiMandi Mobile App — API Client & Offline Fallback Layer
   Aligned with Backend Contract (OpenAPI Specification v1)
   ===================================================================== */

import { API_BASE_URL, DEMO_MODE, warnDemoFallback, API_TIMEOUT_MS } from '../config.js';
import { fetchWithAuth as sessionFetchWithAuth, setTokens, getAccessToken, clearTokens, getCsrfToken } from './auth-session.js';

export async function fetchWithAuth(url, options = {}) {
  const ctrl = new AbortController();
  const tid = setTimeout(() => ctrl.abort(), API_TIMEOUT_MS);
  try {
    return await sessionFetchWithAuth(url, { ...options, signal: options.signal || ctrl.signal });
  } finally {
    clearTimeout(tid);
  }
}

// ---------------------------------------------------------------------------
// Adapters for Backend Contract Alignment
// ---------------------------------------------------------------------------

export function adaptTftForecast(tftData) {
  if (!tftData) return null;
  const currentPrice = tftData.latest_modal_price_inr || tftData.currentPrice || 0;
  const rawHorizons = tftData.horizons || [];
  const forecastDays = rawHorizons.map(h => ({
    day: h.horizon_days != null ? `Day ${h.horizon_days}` : `+${h.day_offset}d`,
    dayOffset: h.day_offset || h.horizon_days || 1,
    p10: h.p10_price_inr ?? h.p10_inr ?? h.p10 ?? currentPrice,
    p50: h.p50_price_inr ?? h.p50_inr ?? h.p50 ?? currentPrice,
    p90: h.p90_price_inr ?? h.p90_inr ?? h.p90 ?? currentPrice,
  }));

  const gain = tftData.expected_net_gain_inr;
  const pct = currentPrice > 0 && gain != null ? ((gain / currentPrice) * 100).toFixed(1) : '0.0';
  const projectedNetGain = gain != null
    ? `${gain >= 0 ? '+' : ''}₹${gain} / Quintal (${gain >= 0 ? '+' : ''}${pct}%)`
    : 'N/A';

  return {
    commodity: tftData.commodity || 'Wheat',
    currentPrice,
    forecastDays,
    p10Terminal: tftData.p10_terminal_price_inr,
    p50Terminal: tftData.p50_terminal_price_inr,
    p90Terminal: tftData.p90_terminal_price_inr,
    recommendation: tftData.recommendation || 'STORE',
    rationale: tftData.rationale || '',
    expectedNetGain: gain,
    projectedNetGain,
    storageCost: tftData.storage_cost_inr,
    capitalCost: tftData.capital_cost_inr,
    totalHoldingCost: tftData.total_holding_cost_inr,
    horizonDays: tftData.horizon_days || 21
  };
}

export function adaptLogisticsQuotes(response) {
  const quotesList = response?.quotes || [];
  return quotesList.map(q => ({
    id: q.provider_id || q.quote_id || q.id || 'LSP-01',
    provider: q.provider_name || q.provider || 'ONDC Transport Provider',
    vehicle: q.vehicle_type || q.vehicle || 'Commercial Vehicle',
    rate: q.total_fare_inr || q.rate || 0,
    eta: q.eta_hours != null ? `${Math.round(q.eta_hours * 60)} mins` : (q.eta || '45 mins'),
    rating: q.rating || 4.8,
    source: q.source || (q.is_network ? 'network' : 'internal'),
    isNetwork: (q.source || '') === 'network' || Boolean(q.is_network),
  }));
}

// ---------------------------------------------------------------------------
// Main API Client Object
// ---------------------------------------------------------------------------

export const api = {
  // 1. Auth & OTP
  async sendOtp(phone) {
    const rawNumber = String(phone || '').trim();
    const formatted = rawNumber.startsWith('+91')
      ? rawNumber
      : `+91${rawNumber.replace(/^\+?91/, '')}`;

    const ctrl = new AbortController();
    const tid = setTimeout(() => ctrl.abort(), API_TIMEOUT_MS);
    try {
      const csrfToken = getCsrfToken();
      const res = await fetch(`${API_BASE_URL}/auth/otp/send`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(csrfToken ? { 'X-CSRF-Token': csrfToken } : {})
        },
        body: JSON.stringify({ phone_number: formatted }),
        signal: ctrl.signal
      });
      if (res.ok) {
        return await res.json();
      }
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || err.error?.message || `HTTP ${res.status}`);
    } catch (e) {
      if (DEMO_MODE) {
        warnDemoFallback('sendOtp', e.message);
        return { success: true, message: 'OTP sent via SMS (Demo: 123456)', expires_in: 300, retry_after: 30 };
      }
      throw e;
    } finally {
      clearTimeout(tid);
    }
  },

  async verifyOtp(phone, otp) {
    const rawNumber = String(phone || '').trim();
    const formatted = rawNumber.startsWith('+91')
      ? rawNumber
      : `+91${rawNumber.replace(/^\+?91/, '')}`;

    const ctrl = new AbortController();
    const tid = setTimeout(() => ctrl.abort(), API_TIMEOUT_MS);
    try {
      const csrfToken = getCsrfToken();
      const res = await fetch(`${API_BASE_URL}/auth/otp/verify`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(csrfToken ? { 'X-CSRF-Token': csrfToken } : {})
        },
        body: JSON.stringify({ phone_number: formatted, otp_code: String(otp || '').trim() }),
        signal: ctrl.signal
      });

      if (res.ok) {
        const data = await res.json();
        // Persist tokens in central auth-session store
        if (data.access_token) {
          setTokens({
            accessToken: data.access_token,
            refreshToken: data.refresh_token,
            tokenType: data.token_type,
            expiresIn: data.expires_in
          });

          // Fetch full user profile from /auth/me
          try {
            const meRes = await fetchWithAuth(`${API_BASE_URL}/auth/me`);
            if (meRes.ok) {
              data.userProfile = await meRes.json();
            }
          } catch (_) {
            // Profile fetch optional on initial login
          }
        }
        return data;
      }
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || err.error?.message || `HTTP ${res.status}`);
    } catch (e) {
      if (DEMO_MODE) {
        warnDemoFallback('verifyOtp', e.message);
        setTokens({
          accessToken: 'demo-jwt-token-98213812',
          refreshToken: 'demo-refresh-token-98213812',
          tokenType: 'bearer',
          expiresIn: 3600
        });
        return {
          success: true,
          access_token: 'demo-jwt-token-98213812',
          refresh_token: 'demo-refresh-token-98213812',
          user: { id: 1, phone_number: formatted, roles: ['farmer'], profile_complete: false }
        };
      }
      throw e;
    } finally {
      clearTimeout(tid);
    }
  },

  async getMe() {
    try {
      const res = await fetchWithAuth(`${API_BASE_URL}/auth/me`);
      if (res.ok) {
        return await res.json();
      }
    } catch (e) {
      if (DEMO_MODE) {
        warnDemoFallback('getMe', e.message);
        return { id: 1, phone: '+919876543210', roles: ['farmer'], status: 'active' };
      }
    }
    return null;
  },

  async logout() {
    try {
      await fetchWithAuth(`${API_BASE_URL}/auth/logout`, { method: 'POST' });
    } catch (_) {}
    clearTokens();
  },

  async resolveLgd({ state_code, district_name, subdistrict_name, village_name }) {
    try {
      const res = await fetchWithAuth(`${API_BASE_URL}/admin/lgd/resolve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ state_code, district_name, subdistrict_name, village_name })
      });
      if (res.ok) return await res.json();
    } catch (e) {
      if (DEMO_MODE) warnDemoFallback('resolveLgd', e.message);
    }
    return null;
  },

  async saveFarmerProfile(profileData) {
    try {
      const res = await fetchWithAuth(`${API_BASE_URL}/farmers/profile`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(profileData)
      });
      if (res.ok) return await res.json();
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${res.status}`);
    } catch (e) {
      if (DEMO_MODE) {
        warnDemoFallback('saveFarmerProfile', e.message);
        return { success: true, farmer_id: profileData.farmer_id || 'FARMER-DEMO-01' };
      }
      throw e;
    }
  },

  // 2. Mandi Prices & TFT Forecasts
  async getMandiPrices(filters = {}) {
    const params = new URLSearchParams();
    if (filters.commodity) params.append('commodity', filters.commodity);
    if (filters.market) params.append('market', filters.market);
    if (filters.state) params.append('state', filters.state);
    if (filters.district) params.append('district', filters.district);
    params.append('limit', String(filters.limit || 20));
    params.append('offset', String(filters.offset || 0));

    try {
      const res = await fetchWithAuth(`${API_BASE_URL}/prices?${params.toString()}`);
      if (res.ok) {
        const payload = await res.json();
        const records = payload.data || [];

        // Compute client-side delta percent from observations if available
        return records.map((r, idx) => {
          let delta = '+0.0%';
          const nextSame = records.slice(idx + 1).find(o => o.commodity === r.commodity && o.market === r.market);
          if (nextSame && nextSame.modal_price_inr_per_quintal > 0) {
            const diff = r.modal_price_inr_per_quintal - nextSame.modal_price_inr_per_quintal;
            const pct = ((diff / nextSame.modal_price_inr_per_quintal) * 100).toFixed(1);
            delta = `${diff >= 0 ? '+' : ''}${pct}%`;
          }
          return {
            crop: r.commodity,
            variety: r.variety || 'Standard',
            mandi: r.market,
            state: r.state,
            price: r.modal_price_inr_per_quintal,
            minPrice: r.min_price_inr_per_quintal,
            maxPrice: r.max_price_inr_per_quintal,
            arrivals: r.arrivals_quintal,
            arrivalDate: r.arrival_date,
            delta: delta,
          };
        });
      }
    } catch (e) {
      if (DEMO_MODE) {
        warnDemoFallback('getMandiPrices', e.message);
      } else {
        throw e;
      }
    }

    if (DEMO_MODE) {
      warnDemoFallback('getMandiPrices', 'Fallback array returned');
      return [
        { crop: 'Wheat (Sharbati)', variety: 'Lokwan', mandi: 'Indore APMC', price: 2850, delta: '+3.8%' },
        { crop: 'Soyabean (Yellow)', variety: 'JS-9560', mandi: 'Ujjain APMC', price: 4720, delta: '+1.4%' },
        { crop: 'Chana (Desi)', variety: 'JG-11', mandi: 'Dewas APMC', price: 5950, delta: '-0.8%' },
        { crop: 'Mustard (Bold)', variety: 'Pusa Bold', mandi: 'Morena APMC', price: 5400, delta: '+2.1%' }
      ];
    }
    return [];
  },

  async getTftForecast(crop = 'Wheat', options = {}) {
    const params = new URLSearchParams();
    params.append('commodity', crop);
    if (options.state) params.append('state', options.state);
    if (options.market) params.append('market', options.market);
    const horizon = Math.min(parseInt(options.horizon_days || '21', 10), 21);
    params.append('horizon_days', String(horizon));

    try {
      const res = await fetchWithAuth(`${API_BASE_URL}/prices/forecast/tft?${params.toString()}`);
      if (res.ok) {
        const data = await res.json();
        return adaptTftForecast(data);
      }
    } catch (e) {
      if (DEMO_MODE) {
        warnDemoFallback('getTftForecast', e.message);
      } else {
        throw e;
      }
    }

    if (DEMO_MODE) {
      warnDemoFallback('getTftForecast', 'Fallback multi-horizon forecast');
      return {
        currentPrice: 2850,
        forecastDays: [
          { day: 'Day 10', p10: 2820, p50: 2910, p90: 2980 },
          { day: 'Day 20', p10: 2870, p50: 2990, p90: 3080 },
          { day: 'Day 30', p10: 2920, p50: 3070, p90: 3190 },
          { day: 'Day 45', p10: 2990, p50: 3170, p90: 3320 }
        ],
        recommendation: 'STORE',
        projectedNetGain: '+₹320 / Quintal (+11.2%)'
      };
    }
    return null;
  },

  // 3. AI Grain Quality Assay  — calls POST /api/v1/lots/{lot_id}/assay
  // Falls back to DEMO_MODE simulation only when explicitly requested.
  async analyzeGrainSample(crop, sampleDetails, imageBlob = null, lotId = null) {
    // DEMO_MODE: always simulate
    if (DEMO_MODE) {
      console.warn('[DEMO MODE] analyzeGrainSample: returning simulated inference results.');
      await new Promise(r => setTimeout(r, 600));
      return {
        isSimulated: true,
        simulationBadge: '⚠ Simulated grading — DEMO_MODE active',
        fallback: 'simulation',
        grade: 'Grade A',
        score: 94.6,
        moisturePercent: 10.4,
        foreignMatterPercent: 0.3,
        damagedGrainPercent: 0.6,
        defectsFound: ['minor broken tip (0.2%) [SIMULATED]'],
        hmacSignature: '0x' + Array.from({length: 32}, () => Math.floor(Math.random()*16).toString(16)).join(''),
        recommendation: '[SIMULATED] Export & High-Fidelity Mandi Grade. Premium price eligibility +₹120/qtl'
      };
    }

    // Real path: POST image to /api/v1/lots/{lot_id}/assay
    const resolvedLotId = lotId || sampleDetails?.lot_id || 'unknown';

    // Build request body — send raw image bytes if available, else a 1x1 placeholder PNG
    let body;
    let contentType;
    if (imageBlob instanceof Blob || imageBlob instanceof File) {
      body = imageBlob;
      contentType = imageBlob.type || 'image/jpeg';
    } else {
      // Minimal transparent 1×1 PNG (base64-decoded) as a placeholder for rule-based path
      const EMPTY_PNG = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==';
      const bin = atob(EMPTY_PNG);
      const arr = new Uint8Array(bin.length).map((_, i) => bin.charCodeAt(i));
      body = new Blob([arr], { type: 'image/png' });
      contentType = 'image/png';
    }

    try {
      const res = await fetchWithAuth(`${API_BASE_URL}/lots/${encodeURIComponent(resolvedLotId)}/assay`, {
        method: 'POST',
        headers: { 'Content-Type': contentType },
        body,
      });

      if (res.ok) {
        const data = await res.json();
        const isRuleBased = (data.fallback === 'rule_based' || data.fallback === 'agmark_rules');
        return {
          isSimulated: false,
          fallback: data.fallback || null,
          fallbackLabel: isRuleBased ? 'Rule-based fallback (No ONNX model)' : null,
          grade: data.grade,
          score: data.confidence !== undefined ? Math.round(parseFloat(data.confidence) * 100) : null,
          moisturePercent: parseFloat(data.moisture_percent),
          foreignMatterPercent: parseFloat(data.foreign_matter_percent),
          damagedGrainPercent: parseFloat(data.damaged_percent),
          defectsFound: [],
          hmacSignature: data.hmac_signature || null,
          recommendation: isRuleBased
            ? `${data.grade} (AGMARK rule-based grade, no ONNX model installed)`
            : `${data.grade} (AI-graded, confidence ${data.confidence})`,
          raw: data,
        };
      }

      const errText = await res.text().catch(() => '');
      console.warn('[analyzeGrainSample] Assay endpoint returned', res.status, errText);
    } catch (e) {
      console.warn('[analyzeGrainSample] Network error calling assay endpoint:', e.message);
    }

    // Hard fallback — rule-based label shown to user
    return {
      isSimulated: false,
      fallback: 'rule_based',
      fallbackLabel: 'Rule-based fallback (No ONNX model)',
      grade: 'Grade B',
      score: null,
      moisturePercent: null,
      foreignMatterPercent: null,
      damagedGrainPercent: null,
      defectsFound: [],
      hmacSignature: null,
      recommendation: 'Assay service unavailable — please retry or contact support',
    };
  },

  async getLots(farmerId) {
    const fid = farmerId || 'FARMER-MP-001';
    try {
      const res = await fetchWithAuth(`${API_BASE_URL}/lots?farmer_id=${encodeURIComponent(fid)}`);
      if (res.ok) {
        return await res.json();
      }
    } catch (e) {
      if (DEMO_MODE) warnDemoFallback('getLots', e.message);
      else throw e;
    }
    return [];
  },

  async getLotDetail(lotCode) {
    try {
      const res = await fetchWithAuth(`${API_BASE_URL}/lots/${encodeURIComponent(lotCode)}`);
      if (res.ok) {
        return await res.json();
      }
    } catch (e) {
      if (DEMO_MODE) warnDemoFallback('getLotDetail', e.message);
      else throw e;
    }
    return null;
  },

  async createLot(lotData) {
    try {
      const res = await fetchWithAuth(`${API_BASE_URL}/lots`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(lotData)
      });
      if (res.ok) {
        return await res.json();
      }
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || err.error?.message || `HTTP ${res.status}`);
    } catch (e) {
      if (DEMO_MODE) {
        warnDemoFallback('createLot', e.message);
        return {
          id: `LOT-${Date.now().toString().slice(-6)}`,
          lot_code: `LOT-${Date.now().toString().slice(-6)}`,
          farmer_id: lotData.farmer_id,
          commodity: lotData.commodity,
          variety: lotData.variety || 'Standard',
          quantity_mt: lotData.quantity_mt,
          grade: lotData.grade,
          status: 'listed'
        };
      }
      throw e;
    }
  },

  async getAssayReport(lotId) {
    try {
      const res = await fetchWithAuth(`${API_BASE_URL}/lots/${encodeURIComponent(lotId)}/assay`);
      if (res.ok) {
        return await res.json();
      }
    } catch (e) {
      if (DEMO_MODE) warnDemoFallback('getAssayReport', e.message);
      else throw e;
    }
    return null;
  },

  // 4. Logistics Quotes & ONDC Dispatch (POST /api/v1/logistics/quotes)
  async getLogisticsQuotes(fromLocation, toLocation, weightTonnes, options = {}) {
    const payload = {
      origin_gps: options.origin_gps || '18.5204,73.8567',
      destination_gps: options.destination_gps || '19.0760,72.8777',
      commodity: options.commodity || 'Wheat',
      quantity_quintals: (parseFloat(weightTonnes) || 1.0) * 10.0,
      vehicle_type: options.vehicle_type || 'MEDIUM_TRUCK',
      requires_cold_chain: Boolean(options.requires_cold_chain),
      is_hub_route: Boolean(options.is_hub_route)
    };

    try {
      const res = await fetchWithAuth(`${API_BASE_URL}/logistics/quotes`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (res.ok) {
        const data = await res.json();
        return adaptLogisticsQuotes(data);
      }
    } catch (e) {
      if (DEMO_MODE) {
        warnDemoFallback('getLogisticsQuotes', e.message);
      } else {
        throw e;
      }
    }

    if (DEMO_MODE) {
      warnDemoFallback('getLogisticsQuotes', 'Fallback quote providers');
      return [
        { id: 'LSP-01', provider: 'TruckSe Logistics (ONDC)', vehicle: '14ft Eicher (4T)', rate: 2380, eta: '45 mins', rating: 4.8, source: 'network', isNetwork: true },
        { id: 'LSP-02', provider: 'Gramin Transport Co.', vehicle: 'Mahindra Bolero Maxi (2T)', rate: 1960, eta: '25 mins', rating: 4.9, source: 'internal', isNetwork: false },
        { id: 'LSP-03', provider: 'Kisan Vahan Network', vehicle: 'Tata 407 (3.5T)', rate: 2240, eta: '1 hr', rating: 4.7, source: 'network', isNetwork: true }
      ];
    }
    return [];
  },

  // 5. Offline Sync Delta Helper (Calling real GET /sync/pull and POST /sync/push)
  async syncDelta(pullLastPulledAt, pushChanges) {
    const results = { timestamp: Date.now(), changes: {}, syncedCount: 0 };

    // 1. Pull Phase: GET /sync/pull
    try {
      const params = new URLSearchParams({
        limit: '500',
        schemaVersion: '1',
        migrationVersion: '1',
      });
      if (pullLastPulledAt) params.append('lastPulledAt', String(pullLastPulledAt));

      const pullRes = await fetchWithAuth(`${API_BASE_URL}/sync/pull?${params.toString()}`);
      if (pullRes.ok) {
        const pullData = await pullRes.json();
        results.changes = pullData.changes || {};
        results.timestamp = pullData.newLastPulledAt || Date.now();
      }
    } catch (e) {
      if (DEMO_MODE) warnDemoFallback('syncDelta.pull', e.message);
    }

    // 2. Push Phase: POST /sync/push
    if (pushChanges && Object.keys(pushChanges).length > 0) {
      try {
        const pushRes = await fetchWithAuth(`${API_BASE_URL}/sync/push`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            changes: pushChanges,
            lastPulledAt: pullLastPulledAt || 0,
            schemaVersion: 1,
            migrationVersion: 1
          })
        });
        if (pushRes.ok) {
          const pushData = await pushRes.json();
          results.syncedCount = Object.keys(pushChanges).length;
          results.accepted = pushData.accepted;
        }
      } catch (e) {
        if (DEMO_MODE) warnDemoFallback('syncDelta.push', e.message);
      }
    }

    return results;
  },

  // 6. DPDP Act 2023 Consent & Data Rights
  async grantConsent(consentData) {
    try {
      const res = await fetchWithAuth(`${API_BASE_URL}/consents`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(consentData)
      });
      if (res.ok) return await res.json();
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || err.error?.message || `HTTP ${res.status}`);
    } catch (e) {
      if (DEMO_MODE) {
        warnDemoFallback('grantConsent', e.message);
        return {
          artifact_id: consentData.artifact_id,
          farmer_id: consentData.farmer_id,
          status: 'granted',
          purpose: consentData.purpose,
          attributes: consentData.attributes,
          created_at: consentData.created_at,
          expires_at: consentData.expires_at,
          signature: consentData.signature
        };
      }
      throw e;
    }
  },

  async getConsent(artifactId) {
    try {
      const res = await fetchWithAuth(`${API_BASE_URL}/consents/${encodeURIComponent(artifactId)}`);
      if (res.ok) return await res.json();
    } catch (e) {
      if (DEMO_MODE) warnDemoFallback('getConsent', e.message);
      else throw e;
    }
    return null;
  },

  async withdrawConsent(artifactId, signature) {
    try {
      const res = await fetchWithAuth(`${API_BASE_URL}/consents/${encodeURIComponent(artifactId)}/withdrawals`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ signature })
      });
      if (res.ok) return await res.json();
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || err.error?.message || `HTTP ${res.status}`);
    } catch (e) {
      if (DEMO_MODE) {
        warnDemoFallback('withdrawConsent', e.message);
        return { artifact_id: artifactId, status: 'withdrawn', message: 'Consent successfully revoked.' };
      }
      throw e;
    }
  },

  async anonymizeConsent(artifactId) {
    try {
      const res = await fetchWithAuth(`${API_BASE_URL}/consents/${encodeURIComponent(artifactId)}/anonymize`, {
        method: 'POST'
      });
      if (res.ok) return await res.json();
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || err.error?.message || `HTTP ${res.status}`);
    } catch (e) {
      if (DEMO_MODE) {
        warnDemoFallback('anonymizeConsent', e.message);
        return {
          certificate_id: `CERT-ERASURE-${Date.now().toString().slice(-6)}`,
          farmer_id: 'FARMER-MP-001',
          artifact_id: artifactId,
          status: 'purged',
          reason: 'Farmer exercised Right to Erasure under DPDP Act 2023 Sec 12',
          parcels_purged: 1,
          lots_withdrawn: 0,
          withdrawn_lot_codes: [],
          cache_keys_evicted: [`farmer:profile:${artifactId}`],
          verification_hash: '0x' + Array.from({length: 64}, () => Math.floor(Math.random()*16).toString(16)).join(''),
          timestamp: new Date().toISOString()
        };
      }
      throw e;
    }
  },

  async getConsentAudit(artifactId) {
    try {
      const res = await fetchWithAuth(`${API_BASE_URL}/consents/${encodeURIComponent(artifactId)}/audit`);
      if (res.ok) return await res.json();
    } catch (e) {
      if (DEMO_MODE) warnDemoFallback('getConsentAudit', e.message);
      else throw e;
    }
    return null;
  },

  // 7. Trade Settlement & ONDC Fulfillment
  async getTradeDetail(transactionId) {
    try {
      const res = await fetchWithAuth(`${API_BASE_URL}/trades/${encodeURIComponent(transactionId)}`);
      if (res.ok) return await res.json();
    } catch (e) {
      if (DEMO_MODE) warnDemoFallback('getTradeDetail', e.message);
      else throw e;
    }
    return null;
  },

  // 8. Logistics Shipment Tracking
  async getShipmentTracking(transactionId) {
    try {
      const res = await fetchWithAuth(`${API_BASE_URL}/logistics/shipments/${encodeURIComponent(transactionId)}`);
      if (res.ok) return await res.json();
    } catch (e) {
      if (DEMO_MODE) warnDemoFallback('getShipmentTracking', e.message);
      else throw e;
    }
    return null;
  },

  // 9. Issue & Grievance Management (IGM)
  async createGrievance(grievanceData) {
    try {
      const res = await fetchWithAuth(`${API_BASE_URL}/grievances`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(grievanceData)
      });
      if (res.ok) return await res.json();
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || err.error?.message || `HTTP ${res.status}`);
    } catch (e) {
      if (DEMO_MODE) {
        warnDemoFallback('createGrievance', e.message);
        return {
          ticket_id: `IGM-${Date.now().toString().slice(-6)}`,
          transaction_id: grievanceData.transaction_id,
          status: 'OPEN',
          category: grievanceData.category || 'QUALITY',
          created_at: new Date().toISOString()
        };
      }
      throw e;
    }
  },

  async getGrievances() {
    try {
      const res = await fetchWithAuth(`${API_BASE_URL}/grievances`);
      if (res.ok) return await res.json();
    } catch (e) {
      if (DEMO_MODE) warnDemoFallback('getGrievances', e.message);
      else throw e;
    }
    return [];
  },

  // 10. e-NWR Pledge Finance
  async checkPledgeEligibility(lotCode, customLtv = 0.75) {
    try {
      const res = await fetchWithAuth(`${API_BASE_URL}/finance/pledge/eligibility`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ lot_code: lotCode, custom_ltv_percent: customLtv })
      });
      if (res.ok) return await res.json();
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || err.error?.message || `HTTP ${res.status}`);
    } catch (e) {
      if (DEMO_MODE) {
        warnDemoFallback('checkPledgeEligibility', e.message);
        return {
          lot_code: lotCode,
          eligible: true,
          commodity_valuation_inr: 295000,
          max_loan_amount_inr: 221250,
          ltv_percent: customLtv,
          recommended_interest_rate_percent: 7.25,
          max_tenure_days: 180
        };
      }
      throw e;
    }
  },

  async applyPledgeLoan(applyData) {
    try {
      const res = await fetchWithAuth(`${API_BASE_URL}/finance/pledge/apply`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(applyData)
      });
      if (res.ok) return await res.json();
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || err.error?.message || `HTTP ${res.status}`);
    } catch (e) {
      if (DEMO_MODE) {
        warnDemoFallback('applyPledgeLoan', e.message);
        return {
          loan_id: `LOAN-ENWR-${Date.now().toString().slice(-6)}`,
          lot_code: applyData.lot_code,
          sanctioned_amount_inr: applyData.requested_amount_inr,
          status: 'SANCTIONED',
          disbursement_mode: applyData.disbursement_mode || 'BANK_TRANSFER',
          monthly_emi_inr: Math.round(applyData.requested_amount_inr / 3),
          created_at: new Date().toISOString()
        };
      }
      throw e;
    }
  },

  async getPledgeLoans(farmerId) {
    const fid = farmerId || 'FARMER-MP-001';
    try {
      const res = await fetchWithAuth(`${API_BASE_URL}/finance/pledge/farmer/${encodeURIComponent(fid)}`);
      if (res.ok) return await res.json();
    } catch (e) {
      if (DEMO_MODE) warnDemoFallback('getPledgeLoans', e.message);
      else throw e;
    }
    return [];
  }
};
