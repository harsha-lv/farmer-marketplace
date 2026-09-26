/* =====================================================================
   MittiMandi Mobile App — Main Router & Sync Event Controller
   ===================================================================== */

import { localDb } from './db.js';
import { store } from './state.js';
import { syncEngine } from './sync.js';
import { api } from './api.js';
import { SYNC_POLL_INTERVAL_MS, DEMO_MODE } from '../config.js';
import { renderSplash, renderLanguage, renderLogin, renderOtp, renderRole } from './screens/auth.js';
import { renderOnboarding } from './screens/onboarding.js';
import { renderDashboard } from './screens/dashboard.js';
import { renderLotsList, renderLotCreate, renderLotDetail, setLotCommodityFilter, setLotGradeFilter, setSelectedLotId } from './screens/lots.js';
import { renderMarketIntel, setActiveMarketCommodity, setActiveMarketHorizon, fetchMarketData, setSearchQuery } from './screens/market.js';
import { renderTrades, renderAgreementCert } from './screens/trades.js';
import { renderTransport } from './screens/transport.js';
import { renderStorage } from './screens/storage.js';
import { renderFinance, setPledgeEligibility, addPledgeLoan } from './screens/finance.js';
import { renderOffline } from './screens/offline.js';
import { renderConsent, setErasureCert, setAuditTrailData, getConsentsList } from './screens/consent.js';
import { renderGrievance, getGrievancesList } from './screens/grievance.js';
import { showToast } from './components/toast.js';
import { renderGlobalOfflineBanner } from './components/offline-banner.js';
import { modalAlert, modalConfirm } from './components/modal.js';
import { onSessionExpired } from './auth-session.js';

class AppRouter {
  constructor() {
    this.history = [];
    this.screens = {
      'splash': renderSplash,
      'auth-language': renderLanguage,
      'auth-login': renderLogin,
      'auth-otp': renderOtp,
      'auth-role': renderRole,
      'onboarding': renderOnboarding,
      'dashboard': renderDashboard,
      'lots-list': renderLotsList,
      'lots-create': renderLotCreate,
      'lot-detail': renderLotDetail,
      'market-intel': renderMarketIntel,
      'trades-negotiate': renderTrades,
      'agreement-cert': renderAgreementCert,
      'transport': renderTransport,
      'storage': renderStorage,
      'finance': renderFinance,
      'offline-sync': renderOffline,
      'consent': renderConsent,
      'grievances': renderGrievance
    };
  }

  navigate(screenId, addToHistory = true) {
    if (!this.screens[screenId]) {
      console.error(`Screen ${screenId} not found`);
      return;
    }

    // Onboarding Gate: If user is verified but profile is incomplete, nudge & route to onboarding
    const user = store.get('user') || {};
    if (user.verified && user.profileComplete === false && screenId !== 'onboarding' && screenId !== 'splash' && !screenId.startsWith('auth-')) {
      showToast('⚠️ Please complete your profile to access marketplace features.');
      screenId = 'onboarding';
    }

    if (addToHistory && store.get('currentScreen') !== screenId) {
      this.history.push(store.get('currentScreen'));
    }

    store.set('currentScreen', screenId);
    this.updateActiveDockItem(screenId);
    this.updateTopFlowSelector(screenId);
    this.render();
  }

  goBack() {
    if (this.history.length > 0) {
      const prev = this.history.pop();
      this.navigate(prev, false);
    } else {
      this.navigate('dashboard', false);
    }
  }

  updateActiveDockItem(screenId) {
    let tab = 'home';
    if (screenId.includes('lot')) tab = 'lots';
    else if (screenId.includes('market')) tab = 'market';
    else if (screenId.includes('trade') || screenId.includes('agreement')) tab = 'trades';
    else if (screenId.includes('transport') || screenId.includes('storage') || screenId.includes('finance')) tab = 'logistics';
    store.set('activeTab', tab);
  }

  updateTopFlowSelector(screenId) {
    document.querySelectorAll('.flow-btn').forEach(btn => {
      if (btn.dataset.screen === screenId) {
        btn.classList.add('active');
        btn.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
      } else {
        btn.classList.remove('active');
      }
    });
  }

  render() {
    const screenId = store.get('currentScreen');
    const viewport = document.getElementById('screen-container');
    const header = document.getElementById('app-header');
    const dock = document.getElementById('bottom-dock');

    if (!viewport) return;

    // Header visibility (hidden on splash)
    if (screenId === 'splash') {
      if (header) {
        header.classList.add('hidden');
        header.style.display = 'none';
      }
      if (dock) {
        dock.classList.add('hidden');
        dock.style.display = 'none';
      }
    } else {
      if (header) {
        header.classList.remove('hidden');
        header.style.display = 'flex';
        this.renderHeader(screenId);
      }
      if (dock) {
        if (screenId.startsWith('auth-') || screenId === 'onboarding') {
          dock.classList.add('hidden');
          dock.style.display = 'none';
        } else {
          dock.classList.remove('hidden');
          dock.style.display = 'flex';
          this.renderDock();
        }
      }
    }

    // Render screen body + Global Offline/Conflict Banner (F8)
    const renderFn = this.screens[screenId];
    const bannerHtml = (screenId !== 'splash' && !screenId.startsWith('auth-')) ? renderGlobalOfflineBanner() : '';
    try {
      viewport.innerHTML = bannerHtml + (renderFn ? renderFn() : `<div>Screen not found</div>`);
    } catch (err) {
      console.error('[Router] Screen render error:', err);
      viewport.innerHTML = '<div>Screen Error. <button data-action="nav" data-screen="dashboard">Go Home</button></div>';
    }
    viewport.scrollTop = 0;

    // Post-render asynchronous DOM updates for offline hub
    if (screenId === 'offline-sync') {
      this.renderOfflineHubAsyncDetails();
    }
  }

  async renderOfflineHubAsyncDetails() {
    const lastPulledAt = await localDb.getMeta('lastPulledAt', null);
    const lastPulledEl = document.getElementById('display-last-pulled-at');
    if (lastPulledEl) {
      lastPulledEl.textContent = lastPulledAt
        ? `${new Date(lastPulledAt).toLocaleString()} (${lastPulledAt} ms)`
        : 'None (Initial Full Sync Required)';
    }

    const outboxItems = await localDb.getOutboxItems();
    const container = document.getElementById('outbox-items-container');
    if (container) {
      if (outboxItems.length === 0) {
        container.innerHTML = `
          <div class="caption text-muted text-center p-sm rounded bg-black-20">
            ✓ Outbox empty. All local writes are synchronized with server.
          </div>
        `;
      } else {
        container.innerHTML = outboxItems.map(item => `
          <div class="flex-row justify-between items-center p-sm rounded bg-black-20 body-xs">
            <div>
              <span class="font-data text-accent font-semibold">
                ${item.table}.${item.action}
              </span>
              <span class="text-muted">${item.record_id}</span>
            </div>
            <span class="badge badge-warning">QUEUE #${item.queueId}</span>
          </div>
        `).join('');
      }
    }
  }

  renderHeader(screenId) {
    const titleMap = {
      'auth-language': 'Choose Language',
      'auth-login': 'Login with Mobile',
      'auth-otp': 'Verification Code',
      'auth-role': 'Select Role',
      'onboarding': 'Complete Profile',
      'dashboard': 'MittiMandi Kisan',
      'lots-list': 'Produce Inventory',
      'lots-create': 'New Harvest Lot',
      'lot-detail': 'Lot Specifications',
      'market-intel': 'Mandi Intelligence',
      'trades-negotiate': 'Trade Negotiation',
      'agreement-cert': 'Digital Agreement',
      'transport': 'ONDC Logistics',
      'storage': 'Cold Storage (WDRA)',
      'finance': 'Escrow Settlement',
      'offline-sync': 'Offline Sync Hub',
      'consent': 'DPDP Consent & Privacy',
      'grievances': 'ONDC Claims & Grievances'
    };

    const isRoot = screenId === 'dashboard' || screenId === 'splash';
    const title = titleMap[screenId] || 'MittiMandi';

    document.getElementById('header-title').textContent = title;
    const backBtn = document.getElementById('header-back-btn');
    if (backBtn) {
      backBtn.style.display = isRoot ? 'none' : 'flex';
    }

    // Update connection indicator in header
    const netIcon = document.getElementById('header-net-icon');
    if (netIcon) {
      netIcon.textContent = store.get('isOnline') ? '📶' : '✈️';
      netIcon.style.opacity = store.get('isOnline') ? '1' : '0.6';
    }
  }

  renderDock() {
    const activeTab = store.get('activeTab');
    const dockItems = [
      { id: 'home', icon: '🏠', label: 'Home', screen: 'dashboard' },
      { id: 'lots', icon: '🌾', label: 'Produce', screen: 'lots-list' },
      { id: 'market', icon: '📈', label: 'Mandi AI', screen: 'market-intel' },
      { id: 'trades', icon: '🤝', label: 'Trades', screen: 'trades-negotiate' },
      { id: 'logistics', icon: '🚚', label: 'Transit', screen: 'transport' }
    ];

    const dock = document.getElementById('bottom-dock');
    if (dock) {
      dock.innerHTML = dockItems.map(item => `
        <button class="dock-item ${item.id === activeTab ? 'active' : ''}" data-action="nav" data-screen="${item.screen}">
          <span class="dock-icon">${item.icon}</span>
          <span class="dock-label">${item.label}</span>
        </button>
      `).join('');
    }
  }
}

export const router = new AppRouter();
window.appRouter = router;

// ---------------------------------------------------------------------
// Interactive Module Action Handlers (Scoped to Module, Dispatched via ACTION_DISPATCHER)
// ---------------------------------------------------------------------

function setAppLanguage(langCode) {
  store.update('user', u => ({ ...u, language: langCode }));
  showToast(`Language set to ${langCode.toUpperCase()}`);
  router.render();
}

function setUserRole(roleId) {
  store.update('user', u => ({ ...u, role: roleId }));
  showToast(`Role selected: ${roleId.toUpperCase()}`);
  router.render();
}

async function handleSendOtp() {
  const input = document.getElementById('login-phone');
  const raw = (input?.value || '').trim();
  const clean = raw.replace(/\D/g, '');
  const phone = clean.slice(-10);

  if (!/^[6-9]\d{9}$/.test(phone)) {
    showToast('⚠️ Please enter a valid 10-digit mobile number (starts with 6-9).');
    return;
  }

  store.update('user', u => ({ ...u, phone }));
  try {
    const res = await api.sendOtp(phone);
    store.set('otpRetryAfter', res.retry_after || 30);
    showToast(res.message || `OTP sent to +91 ${phone}`);
    router.navigate('auth-otp');
  } catch (err) {
    if (err.message.includes('429') || err.message.includes('Too many')) {
      showToast('⚠️ Too many OTP requests. Please wait before retrying.');
    } else {
      showToast(`Error sending OTP: ${err.message}`);
    }
  }
}

async function handleVerifyOtp() {
  const phone = store.get('user').phone || '9876543210';
  const inputs = document.querySelectorAll('.otp-digit');
  const otpCode = Array.from(inputs).map(i => i.value).join('').trim();
  if (!otpCode) {
    showToast('Please enter the OTP.', 'warning');
    return;
  }

  try {
    const res = await api.verifyOtp(phone, otpCode);
    const role = (res.user?.roles && res.user.roles[0]) || 'farmer';
    const profileComplete = Boolean(res.user?.profile_complete);

    store.update('user', u => ({
      ...u,
      phone: res.user?.phone_number || phone,
      role,
      verified: true,
      profileComplete
    }));

    if (profileComplete) {
      showToast('Identity verified successfully! Welcome.');
      router.navigate('dashboard');
    } else {
      showToast('Welcome! Please complete your profile to continue.');
      router.navigate('onboarding');
    }
  } catch (err) {
    if (err.message.includes('410') || err.message.includes('expired')) {
      showToast('⚠️ OTP has expired. Please request a new OTP.');
    } else if (err.message.includes('429') || err.message.includes('locked')) {
      showToast('⚠️ Account locked due to multiple invalid attempts.');
    } else {
      showToast(`Verification failed: ${err.message}`);
    }
  }
}

async function handleSubmitOnboarding() {
  const name = document.getElementById('onboard-name')?.value || 'Ramesh Patel';
  const stateCode = document.getElementById('onboard-state')?.value || '23';
  const district = document.getElementById('onboard-district')?.value || 'Khargone';
  const village = document.getElementById('onboard-village')?.value || 'Kasrawad';
  const fpo = document.getElementById('onboard-fpo')?.value || 'Nimar Kisan Producer Co.';
  const landAcres = parseFloat(document.getElementById('onboard-land')?.value || '5.0');
  const crop = document.getElementById('onboard-crop')?.value || 'Wheat';

  showToast('Saving profile to farmer registry…');

  try {
    const profileRes = await api.saveFarmerProfile({
      state_lgd_code: stateCode,
      consent_artifact_id: `CONSENT-AGRISTACK-${Date.now()}`,
      name,
      district,
      village,
      fpo,
      land_acres: landAcres,
      primary_crop: crop
    });

    // Re-fetch profile via /auth/me
    const me = await api.getMe();
    if (me && me.roles) {
      store.update('user', u => ({
        ...u,
        role: me.roles[0] || u.role
      }));
    }

    const serverFarmerId = profileRes?.farmer_id || me?.farmer_id || me?.id;

    store.update('user', u => ({
      ...u,
      farmer_id: serverFarmerId || u.farmer_id,
      name,
      location: `${village}, ${district}`,
      fpo,
      profileComplete: true
    }));

    showToast('Profile registered! Welcome to MittiMandi.');
    router.navigate('dashboard');
  } catch (err) {
    showToast(`Profile registration note: ${err.message}`);
  }
}

async function triggerAssay() {
  if (DEMO_MODE) {
    triggerSimulateAssay();
    return;
  }
  const assayBox = document.getElementById('assay-preview-box');
  if (assayBox) assayBox.style.opacity = '0.6';
  showToast('🔬 Running grain assay…');
  try {
    const crop = document.getElementById('lot-crop')?.value || 'Wheat';
    const result = await api.analyzeGrainSample(crop, {});
    const moistureEl = document.getElementById('assay-moisture');
    const foreignEl = document.getElementById('assay-foreign');
    const headerBadgeEl = document.querySelector('#assay-result-card .assay-header .badge');
    if (moistureEl) moistureEl.textContent = result.moisturePercent != null ? `${result.moisturePercent}%` : 'N/A';
    if (foreignEl) foreignEl.textContent = result.foreignMatterPercent != null ? `${result.foreignMatterPercent}%` : 'N/A';
    if (headerBadgeEl) {
      if (result.fallbackLabel) {
        headerBadgeEl.className = 'badge badge-fallback-rule';
        headerBadgeEl.textContent = `⚠ ${result.fallbackLabel}`;
      } else {
        headerBadgeEl.className = 'badge badge-grade-a';
        headerBadgeEl.textContent = `✓ AI Graded — ${result.grade}`;
      }
    }
    showToast(result.fallbackLabel
      ? `⚠ ${result.grade} — ${result.fallbackLabel}`
      : `✓ Assay complete: ${result.grade} (Confidence: ${result.score != null ? result.score + '%' : 'N/A'})`);
  } catch (err) {
    showToast(`Assay error: ${err.message}`);
  } finally {
    if (assayBox) assayBox.style.opacity = '1';
  }
}

function triggerSimulateAssay() {
  console.warn('[DEMO / SIMULATION] triggerSimulateAssay: Using simulated grain assay. No local ONNX vision model loaded.');
  showToast('⚠ DEMO MODE — Simulated grading (mock detection)…');
  setTimeout(() => {
    const moistureEl = document.getElementById('assay-moisture');
    const foreignEl = document.getElementById('assay-foreign');
    if (moistureEl) moistureEl.textContent = '10.2%';
    if (foreignEl) foreignEl.textContent = '0.2%';
    showToast('⚠ DEMO: Simulated Grade A (Score: 95.2%). No real ONNX model loaded.');
  }, 800);
}

async function handleCreateLot() {
  const crop = document.getElementById('lot-crop')?.value || 'Wheat';
  const qty = parseFloat(document.getElementById('lot-qty')?.value || '10.0');
  const price = parseInt(document.getElementById('lot-price')?.value || '2950', 10);
  const randomSuffix = Math.floor(Math.random() * 9000 + 1000);
  const lotId = `LOT-IND-2026-${randomSuffix}`;

  const newLot = {
    id: lotId,
    farmer_id: 'FARMER-MP-001',
    commodity: crop,
    crop: crop,
    variety: 'Sharbati C-306',
    quantity_mt: qty,
    quantity: qty * 10, // quintals
    pricePerQtl: price,
    grade: 'Grade A',
    status: 'draft',
    moisture: '10.4%',
    foreignMatter: '0.3%',
    damagedGrains: '0.5%',
    assayScore: 94.8,
    hmacSeal: '0x' + Array.from({length: 8}, () => Math.floor(Math.random()*16).toString(16)).join('') + '...',
    harvestDate: new Date().toISOString().split('T')[0],
    bidsCount: 0,
    highestBid: price - 30,
    created_at: Date.now(),
    updated_at: Date.now(),
    deleted_at: null
  };

  try {
    // 1. Commit to Local Database (Single Source of Truth)
    await localDb.put('lots', newLot, false); // isRemoteSync = false -> enqueues in outbox
    await store.refreshFromLocalDb();

    const isOnline = store.get('isOnline');
    if (isOnline) {
      showToast(`Lot ${lotId} saved locally! Syncing with server...`);
      syncEngine.triggerSync();
    } else {
      showToast(`Lot ${lotId} saved in local IndexedDB! Buffered in outbox.`);
    }

    router.navigate('lots-list');
  } catch (error) {
    if (error.name === 'SyncQueueCapExceededError') {
      await modalAlert(`⚠️ WRITE REJECTED: ${error.message}\nNo write was silently dropped.`, 'Write Cap Exceeded');
    } else {
      await modalAlert(`Error creating lot: ${error.message}`, 'Creation Error');
    }
  }
}

async function handleDeleteLot(lotId) {
  const targetLotId = lotId || store.get('selectedLotId');
  if (!targetLotId) return;
  const confirmed = await modalConfirm(`Are you sure you want to delete lot ${targetLotId}?`, 'Confirm Delete');
  if (!confirmed) return;

  try {
    await localDb.delete('lots', targetLotId, false);
    await store.refreshFromLocalDb();

    if (store.get('isOnline')) {
      showToast(`Tombstone recorded for ${targetLotId}. Syncing with server...`);
      syncEngine.triggerSync();
    } else {
      showToast(`Tombstone recorded for ${targetLotId} in local outbox.`);
    }

    router.navigate('lots-list');
  } catch (error) {
    await modalAlert(`Error deleting lot: ${error.message}`, 'Delete Error');
  }
}

function handleSendCounterOffer() {
  const input = document.getElementById('counter-price-input');
  const price = parseInt(input?.value || '2940', 10);

  store.update('negotiation', neg => ({
    ...neg,
    farmerTarget: price,
    history: [
      ...neg.history,
      { sender: 'farmer', price, note: `Revised counter-offer for Grade A grain.` }
    ]
  }));

  showToast(`Counter-offer ₹${price}/Qtl submitted!`);
  router.render();
}

function selectTransport(tid) {
  store.set('selectedTransport', tid);
  showToast('Selected logistics provider');
  router.render();
}

function handleConfirmTransport() {
  showToast('Logistics Dispatch Confirmed on ONDC Network! Driver assigned.');
  setTimeout(() => {
    router.navigate('finance');
  }, 1200);
}

function toggleAirplaneMode() {
  const wasOnline = store.get('isOnline');
  const willBeOnline = !wasOnline;

  if (willBeOnline) {
    syncEngine.onConnectivityRegained();
    showToast('📶 Reconnected! Executing Pull-First, then Push...');
  } else {
    syncEngine.onConnectivityLost();
    showToast('✈️ Airplane Mode active. Local IndexedDB is active.');
  }

  router.render();
}

function triggerManualSync() {
  syncEngine.triggerSync();
}

async function clearConflictsLog() {
  await localDb.clearConflicts();
  await store.refreshFromLocalDb();
  showToast('Conflicts log cleared.');
  router.render();
}

async function simulateConflict(conflictResolutionType) {
  const sampleLotId = 'LOT-IND-2026-0012';

  if (conflictResolutionType === 'merged_as_update') {
    await syncEngine.handleServerConflict({
      table: 'lots',
      id: sampleLotId,
      type: 'created_existing_uuid',
      resolution: 'merged_as_update',
      server_version: { id: sampleLotId, commodity: 'Wheat', status: 'registered', quantity_mt: 14.5 },
      client_version: { id: sampleLotId, commodity: 'Wheat', status: 'draft', quantity_mt: 12.0 },
      message: 'Record with this ID already exists on server; merged changes as an update.'
    });
    showToast('Conflict handled: merged_as_update');
  } else if (conflictResolutionType === 'server_won') {
    await syncEngine.handleServerConflict({
      table: 'lots',
      id: sampleLotId,
      type: 'concurrent_update',
      resolution: 'server_won',
      server_version: { id: sampleLotId, status: 'warehoused', quantity_mt: 15.0, updated_at: Date.now() },
      client_version: { id: sampleLotId, status: 'draft', quantity_mt: 12.0, updated_at: Date.now() - 50000 },
      message: 'Concurrent update detected. Server record has newer timestamp; server version retained.'
    });
    showToast('Conflict handled: server_won (Last-Writer-Wins)');
  } else if (conflictResolutionType === 'server_authoritative') {
    await syncEngine.handleServerConflict({
      table: 'market_prices',
      id: '101',
      type: 'read_only_table',
      resolution: 'server_authoritative',
      server_version: { id: '101', commodity: 'Wheat', modal_price_inr: 2850 },
      message: "Table 'market_prices' is server-authoritative. Offline modifications are rejected."
    });
    showToast('Conflict handled: server_authoritative');
  } else if (conflictResolutionType === 'delete_rejected') {
    await syncEngine.handleServerConflict({
      table: 'lots',
      id: sampleLotId,
      type: 'delete_rejected',
      resolution: 'rejected_active_lien_or_listing',
      server_version: { id: sampleLotId, status: 'warehoused', enam_lot_id: 'ENAM-7721' },
      message: 'Cannot delete lot with active e-NAM or ONDC registered listing.'
    });
    showToast('Conflict handled: rejected_active_lien_or_listing');
  }

  await store.refreshFromLocalDb();
  router.render();
}

function simulateTokenExpiry() {
  store.update('session', s => ({ ...s, accessToken: 'expired_invalid_token' }));
  localStorage.setItem('mm_access_token', 'expired_invalid_token');
  showToast('Access token expired. Triggering sync to test 401 refresh...');
  syncEngine.triggerSync();
}

function toggleDeviceFrame() {
  const frame = document.getElementById('device-frame');
  if (!frame) return;
  const isFull = frame.classList.toggle('fullscreen');
  const btn = document.getElementById('toggle-frame-btn');
  if (btn) {
    btn.innerHTML = isFull ? '<span>📱 Mobile Frame</span>' : '<span>🖥️ Fullscreen View</span>';
  }
}

// Clock in mobile status bar
function updateClock() {
  const el = document.getElementById('status-time-clock');
  if (el) {
    const now = new Date();
    el.textContent = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
  }
}
setInterval(updateClock, 10000);
updateClock();

// -----------------------------------------------------------------------
// CSP-Safe Delegated Event Action Dispatcher
// All interactive elements use declarative data-action="..." tokens.
// Handlers are bound purely in JS and invoked without string evaluation.
// -----------------------------------------------------------------------
export function resolveActionTarget(arg1, arg2) {
  if (arg1 && arg1.dataset) return arg1;
  if (arg1 && arg1.target && typeof arg1.target.closest === 'function') {
    return arg1.target.closest('[data-action]') || arg1.target.closest('[data-change]') || arg1.target;
  }
  if (arg2 && arg2.dataset) return arg2;
  if (arg2 && arg2.target && typeof arg2.target.closest === 'function') {
    return arg2.target.closest('[data-action]') || arg2.target.closest('[data-change]') || arg2.target;
  }
  return null;
}

export const ACTION_DISPATCHER = {
  // Navigation & Core Router
  'nav': (e) => {
    const target = resolveActionTarget(e);
    const screen = target?.dataset?.screen || target?.dataset?.navTarget;
    if (screen && router) router.navigate(screen);
  },
  'back': () => {
    if (router) router.goBack();
  },
  'render': () => {
    if (router) router.render();
  },

  // Layout & Shell
  'toggle-frame': () => toggleDeviceFrame(),
  'toggleDeviceFrame': () => toggleDeviceFrame(),

  // Auth & Onboarding Actions
  'set-lang': (e) => {
    const target = resolveActionTarget(e);
    const lang = target?.dataset?.lang;
    if (lang) setAppLanguage(lang);
  },
  'setAppLanguage': (e) => {
    const target = resolveActionTarget(e);
    const lang = target?.dataset?.lang || (typeof e === 'string' ? e : null);
    if (lang) setAppLanguage(lang);
  },
  'set-role': (e) => {
    const target = resolveActionTarget(e);
    const role = target?.dataset?.role;
    if (role) setUserRole(role);
  },
  'setUserRole': (e) => {
    const target = resolveActionTarget(e);
    const role = target?.dataset?.role || (typeof e === 'string' ? e : null);
    if (role) setUserRole(role);
  },
  'send-otp': (e) => handleSendOtp(e),
  'handleSendOtp': (e) => handleSendOtp(e),
  'verify-otp': (e) => handleVerifyOtp(e),
  'handleVerifyOtp': (e) => handleVerifyOtp(e),
  'fill-demo-otp': () => {
    const digits = document.querySelectorAll('.otp-digit');
    if (digits.length) {
      ['1', '2', '3', '4', '5', '6'].forEach((d, i) => {
        if (digits[i]) digits[i].value = d;
      });
    }
    showToast('Demo OTP 123456 auto-filled!');
  },
  'submit-onboarding': (e) => handleSubmitOnboarding(e),
  'handleSubmitOnboarding': (e) => handleSubmitOnboarding(e),
  'logout': async () => {
    if (api && api.logout) await api.logout();
    showToast('Logged out successfully.');
    router.navigate('splash');
  },

  // AI Quality Assay
  'trigger-assay': (e) => triggerAssay(e),
  'triggerAssay': (e) => triggerAssay(e),
  'trigger-simulate-assay': (e) => triggerSimulateAssay(e),
  'triggerSimulateAssay': (e) => triggerSimulateAssay(e),

  // Lot Management
  'create-lot': (e) => handleCreateLot(e),
  'handleCreateLot': (e) => handleCreateLot(e),
  'delete-lot': (e) => {
    const target = resolveActionTarget(e);
    const lotId = target?.dataset?.lotId;
    if (lotId) handleDeleteLot(lotId);
  },
  'handleDeleteLot': (e) => {
    const target = resolveActionTarget(e);
    const lotId = target?.dataset?.lotId || (typeof e === 'string' ? e : null);
    if (lotId) handleDeleteLot(lotId);
  },
  'filter-lot-commodity': (e) => {
    const target = resolveActionTarget(e);
    const c = target?.dataset?.commodity || 'ALL';
    setLotCommodityFilter(c);
    if (router) router.render();
  },
  'filter-lot-grade': (e) => {
    const target = resolveActionTarget(e);
    const g = target?.dataset?.grade || 'ALL';
    setLotGradeFilter(g);
    if (router) router.render();
  },
  'view-lot-detail': (e) => {
    const target = resolveActionTarget(e);
    const lid = target?.dataset?.lotId;
    if (lid) {
      setSelectedLotId(lid);
      if (router) router.navigate('lot-detail');
    }
  },

  // Market & Mandi Intel
  'set-market-commodity': (e) => {
    const target = resolveActionTarget(e);
    const c = target?.dataset?.commodity;
    if (c && typeof setActiveMarketCommodity === 'function') setActiveMarketCommodity(c);
  },
  'set-market-horizon': (e) => {
    const target = resolveActionTarget(e);
    const h = target?.dataset?.horizon;
    if (h && typeof setActiveMarketHorizon === 'function') setActiveMarketHorizon(h);
  },
  'refresh-market-data': () => {
    showToast('Fetching latest Mandi rates & TFT forecast…');
    if (typeof fetchMarketData === 'function') fetchMarketData(true);
  },
  'search-market-mandi': (e) => {
    const target = resolveActionTarget(e);
    const query = target?.value != null ? target.value : (e?.target?.value || (typeof e === 'string' ? e : ''));
    if (typeof setSearchQuery === 'function') setSearchQuery(query);
    if (router) router.render();
  },

  // Trades & Logistics
  'send-counter-offer': (e) => handleSendCounterOffer(e),
  'handleSendCounterOffer': (e) => handleSendCounterOffer(e),
  'select-transport': (e) => {
    const target = resolveActionTarget(e);
    const tid = target?.dataset?.transportId;
    if (tid) selectTransport(tid);
  },
  'selectTransport': (e) => {
    const target = resolveActionTarget(e);
    const tid = target?.dataset?.transportId || (typeof e === 'string' ? e : null);
    if (tid) selectTransport(tid);
  },
  'confirm-transport': (e) => handleConfirmTransport(e),
  'handleConfirmTransport': (e) => handleConfirmTransport(e),

  // Offline Sync & Conflict Simulation
  'toggle-airplane': (e) => toggleAirplaneMode(e),
  'toggleAirplaneMode': (e) => toggleAirplaneMode(e),
  'manual-sync': (e) => triggerManualSync(e),
  'triggerManualSync': (e) => triggerManualSync(e),
  'clear-conflicts': (e) => clearConflictsLog(e),
  'clearConflictsLog': (e) => clearConflictsLog(e),
  'simulate-conflict': (e) => {
    const target = resolveActionTarget(e);
    const type = target?.dataset?.conflictType;
    if (type) simulateConflict(type);
  },
  'simulateConflict': (e) => {
    const target = resolveActionTarget(e);
    const type = target?.dataset?.conflictType || (typeof e === 'string' ? e : null);
    if (type) simulateConflict(type);
  },
  'simulate-token-expiry': (e) => simulateTokenExpiry(e),
  'simulateTokenExpiry': (e) => simulateTokenExpiry(e),
  'update-clock': () => updateClock(),
  'updateClock': () => updateClock(),

  // DPDP Privacy & Consent Actions
  'revoke-consent': async (e) => {
    const target = resolveActionTarget(e);
    const artId = target?.dataset?.artifactId;
    if (!artId) return;
    const sig = 'e5f6a1b2c3d47890123456789abcdef0123456789abcdef0123456789abcdef4';
    try {
      showToast('Revoking consent on server…');
      await api.withdrawConsent(artId, sig);
      const list = getConsentsList();
      const item = list.find(c => c.artifact_id === artId);
      if (item) item.status = 'withdrawn';
      store.set('consents', [...list]);
      showToast(`Consent ${artId} revoked successfully.`);
      if (router) router.render();
    } catch (err) {
      showToast(`Revocation note: ${err.message}`);
    }
  },
  'anonymize-consent': async (e) => {
    const target = resolveActionTarget(e);
    const artId = target?.dataset?.artifactId;
    if (!artId) return;
    try {
      showToast('Executing Right to Erasure (Sec 12 DPDP)…');
      const cert = await api.anonymizeConsent(artId);
      setErasureCert(cert);
      const list = getConsentsList();
      const item = list.find(c => c.artifact_id === artId);
      if (item) item.status = 'purged';
      store.set('consents', [...list]);
      showToast(`Erasure complete: Cert ${cert.certificate_id}`);
      if (router) router.render();
    } catch (err) {
      showToast(`Erasure error: ${err.message}`);
    }
  },
  'view-consent-audit': async (e) => {
    const target = resolveActionTarget(e);
    const artId = target?.dataset?.artifactId;
    if (!artId) return;
    try {
      showToast('Fetching immutable audit trail…');
      const audit = await api.getConsentAudit(artId);
      setAuditTrailData(audit || { artifact_id: artId, events: [] });
      if (router) router.render();
    } catch (err) {
      showToast(`Audit trail note: ${err.message}`);
      setAuditTrailData({ artifact_id: artId });
      if (router) router.render();
    }
  },
  'dismiss-erasure-cert': () => {
    setErasureCert(null);
    if (router) router.render();
  },
  'dismiss-audit-trail': () => {
    setAuditTrailData(null);
    if (router) router.render();
  },
  'open-grant-consent-dialog': async () => {
    const newId = `CONSENT-CUSTOM-${Date.now().toString().slice(-6)}`;
    try {
      await api.grantConsent({
        artifact_id: newId,
        farmer_id: 'FARMER-MP-001',
        purpose: 'New agricultural marketplace analytical processing',
        attributes: ['crop_yield', 'soil_health_card'],
        created_at: new Date().toISOString(),
        expires_at: new Date(Date.now() + 365*24*3600*1000).toISOString(),
        signature: 'f6a1b2c3d4e57890123456789abcdef0123456789abcdef0123456789abcdef5'
      });
      const list = getConsentsList();
      list.unshift({
        artifact_id: newId,
        title: 'Custom Analytical Processing Consent',
        purpose: 'New agricultural marketplace analytical processing',
        attributes: ['crop_yield', 'soil_health_card'],
        status: 'granted',
        created_at: new Date().toISOString(),
        expires_at: new Date(Date.now() + 365*24*3600*1000).toISOString(),
        fiduciary: 'MittiMandi Data Trustee Network',
        signature: 'f6a1b2c3d4e57890123456789abcdef0123456789abcdef0123456789abcdef5'
      });
      store.set('consents', [...list]);
      showToast(`New consent ${newId} granted under DPDP!`);
      if (router) router.render();
    } catch (err) {
      showToast(`Grant consent note: ${err.message}`);
    }
  },

  // Finance & Warehouse Pledge
  'check-pledge-eligibility': async () => {
    const lotCode = document.getElementById('pledge-lot-code')?.value || 'LOT-IND-2026-081';
    showToast('Checking e-NWR pledge loan eligibility…');
    try {
      const res = await api.checkPledgeEligibility(lotCode, 0.75);
      if (typeof setPledgeEligibility === 'function') setPledgeEligibility(res);
      showToast(`Eligible: Max loan ₹${res.max_loan_amount_inr.toLocaleString()} (75% LTV)`);
      if (router) router.render();
    } catch (err) {
      showToast(`Eligibility note: ${err.message}`);
    }
  },
  'apply-pledge-loan': async () => {
    const lotCode = document.getElementById('pledge-lot-code')?.value || 'LOT-IND-2026-081';
    const amount = parseInt(document.getElementById('pledge-amount')?.value || '221250', 10);
    const tenure = parseInt(document.getElementById('pledge-tenure')?.value || '90', 10);
    const mode = document.getElementById('pledge-disburse-mode')?.value || 'BANK_TRANSFER';
    showToast('Submitting e-NWR loan application…');
    try {
      const res = await api.applyPledgeLoan({
        lot_code: lotCode,
        requested_amount_inr: amount,
        tenure_days: tenure,
        disbursement_mode: mode
      });
      if (typeof addPledgeLoan === 'function') {
        addPledgeLoan({
          loan_id: res.loan_id,
          lot_code: lotCode,
          sanctioned_amount_inr: amount,
          disbursement_mode: mode,
          interest_rate: '7.25% p.a.',
          tenure_days: tenure,
          status: 'SANCTIONED',
          disbursed_at: new Date().toISOString(),
          lender: 'State Bank of India (Agri Division)'
        });
      }
      showToast(`Loan ${res.loan_id} sanctioned & queued for disbursement!`);
      if (router) router.render();
    } catch (err) {
      showToast(`Loan application note: ${err.message}`);
    }
  },

  // ONDC IGM Grievances
  'submit-grievance': async () => {
    const cat = document.getElementById('igm-category')?.value || 'QUALITY';
    const txnId = document.getElementById('igm-txn-id')?.value || 'TXN-ITC-2026-081';
    const desc = document.getElementById('igm-desc')?.value || 'Dispute regarding quality assay at warehouse gate';
    showToast('Submitting dispute to ONDC IGM network…');
    try {
      const res = await api.createGrievance({
        transaction_id: txnId,
        category: cat,
        description: desc,
        complainant_info: { role: 'farmer', name: 'Ramesh Patel' }
      });
      const list = typeof getGrievancesList === 'function' ? getGrievancesList() : [];
      list.unshift({
        ticket_id: res.ticket_id,
        transaction_id: txnId,
        category: cat,
        sub_category: 'DISPUTE_RAISED',
        description: desc,
        status: 'OPEN',
        sla_hours_remaining: 24,
        created_at: new Date().toISOString(),
        respondent: 'ITC Agri Business Ltd.'
      });
      store.set('grievances', [...list]);
      showToast(`IGM Ticket ${res.ticket_id} opened. Resolution SLA: 24h.`);
      if (router) router.render();
    } catch (err) {
      showToast(`Grievance note: ${err.message}`);
    }
  },
  'escalate-grievance': (e) => {
    const target = resolveActionTarget(e);
    const tid = target?.dataset?.ticketId;
    const list = typeof getGrievancesList === 'function' ? getGrievancesList() : [];
    const item = list.find(g => g.ticket_id === tid);
    if (item) {
      item.status = 'ESCALATED';
      item.sla_hours_remaining = 6;
    }
    store.set('grievances', [...list]);
    showToast(`Ticket ${tid} escalated to National ONDC Agri Ombudsman!`);
    if (router) router.render();
  },

  // Generic Toast Notification Action
  'toast': (e) => {
    const target = resolveActionTarget(e);
    const msg = target?.dataset?.toastMsg;
    if (msg) showToast(msg);
  }
};

// Boot application & Initialize Local Database
async function initApp() {
  try {
    await localDb.init();
    await store.refreshFromLocalDb();
    console.log('[MittiMandi] Local Database initialized as single source of truth.');

    // If online, perform startup pull-first sync
    if (store.get('isOnline')) {
      syncEngine.triggerSync();
    }

    window.syncEngine = syncEngine;
    setInterval(() => { if(window.syncEngine) window.syncEngine.triggerSync(); }, SYNC_POLL_INTERVAL_MS);
  } catch (err) {
    console.error('[MittiMandi] Startup initialization error:', err);
  }

  router.navigate('splash');
}

// Wire automatic session expiration handler
onSessionExpired(() => {
  showToast('⚠️ Session expired — please sign in again.');
  store.update('user', u => ({ ...u, verified: false }));
  router.navigate('auth-login');
});

// Global Delegated Event Listeners (Zero Inline Handlers)
document.addEventListener('click', (e) => {
  const actionEl = e.target.closest('[data-action]');
  if (!actionEl) return;

  if (actionEl.tagName === 'BUTTON' || actionEl.tagName === 'A') {
    e.preventDefault();
  }

  const action = actionEl.getAttribute('data-action');
  if (action && ACTION_DISPATCHER[action]) {
    try {
      ACTION_DISPATCHER[action](e, actionEl);
    } catch (err) {
      console.error('[DelegatedAction] Error executing:', action, err);
    }
  }
});

document.addEventListener('change', (e) => {
  const changeEl = e.target.closest('[data-change]');
  if (!changeEl) return;
  const action = changeEl.getAttribute('data-change');
  if (action && ACTION_DISPATCHER[action]) {
    try {
      ACTION_DISPATCHER[action](e, changeEl);
    } catch (err) {
      console.error('[DelegatedChange] Error executing:', action, err);
    }
  }
});

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initApp);
} else {
  initApp();
}
