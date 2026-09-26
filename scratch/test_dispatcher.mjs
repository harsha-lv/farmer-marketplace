// Polyfill minimal browser globals for Node.js test environment
globalThis.localStorage = {
  store: {},
  getItem(k) { return this.store[k] || null; },
  setItem(k, v) { this.store[k] = String(v); },
  removeItem(k) { delete this.store[k]; }
};

globalThis.document = {
  getElementById(id) {
    return {
      classList: { add() {}, remove() {}, toggle() {} },
      style: {},
      innerHTML: '',
      scrollTop: 0,
      textContent: '',
      addEventListener() {}
    };
  },
  querySelectorAll() { return []; },
  addEventListener() {}
};

try {
  Object.defineProperty(globalThis.navigator, 'onLine', { value: true, configurable: true });
} catch (_) {}
globalThis.window = globalThis;
globalThis.location = { origin: 'http://127.0.0.1:5500' };
globalThis.addEventListener = () => {};

// Dynamic import after polyfills
const { router, ACTION_DISPATCHER, resolveActionTarget } = await import('../web/scripts/app.js');
const { store } = await import('../web/scripts/state.js');

console.log('--- Testing ACTION_DISPATCHER ---');
console.log('Total actions registered:', Object.keys(ACTION_DISPATCHER).length);

// Verify all required functions exist in ACTION_DISPATCHER
const requiredFunctions = [
  'handleCreateLot', 'create-lot',
  'handleVerifyOtp', 'verify-otp',
  'handleSendOtp', 'send-otp',
  'handleSubmitOnboarding', 'submit-onboarding',
  'triggerAssay', 'trigger-assay',
  'triggerSimulateAssay', 'trigger-simulate-assay',
  'handleDeleteLot', 'delete-lot',
  'handleSendCounterOffer', 'send-counter-offer',
  'selectTransport', 'select-transport',
  'handleConfirmTransport', 'confirm-transport',
  'toggleAirplaneMode', 'toggle-airplane',
  'triggerManualSync', 'manual-sync',
  'clearConflictsLog', 'clear-conflicts',
  'simulateConflict', 'simulate-conflict',
  'simulateTokenExpiry', 'simulate-token-expiry',
  'toggleDeviceFrame', 'toggle-frame',
  'setAppLanguage', 'set-lang',
  'setUserRole', 'set-role',
  'nav', 'back', 'render'
];

let missing = [];
for (const fn of requiredFunctions) {
  if (typeof ACTION_DISPATCHER[fn] !== 'function') {
    missing.push(fn);
  }
}

if (missing.length > 0) {
  console.error('FAIL: Missing functions in ACTION_DISPATCHER:', missing);
  process.exit(1);
} else {
  console.log('SUCCESS: All 19+ functions exist in ACTION_DISPATCHER!');
}

// Verify that all screens render without error
const screens = Object.keys(router.screens);
console.log(`--- Testing All ${screens.length} Screens in AppRouter ---`);
for (const s of screens) {
  try {
    const html = router.screens[s]();
    if (!html || typeof html !== 'string') {
      console.error(`FAIL: Screen '${s}' did not return HTML string.`);
      process.exit(1);
    }
    console.log(`✓ Screen '${s}' renders OK (${html.length} chars)`);
  } catch (err) {
    console.error(`FAIL: Screen '${s}' threw error:`, err);
    process.exit(1);
  }
}

// Test click dispatch mapping simulation
console.log('--- Testing Event Dispatch Mapping ---');
const dummyEvent = {
  target: {
    closest: (selector) => {
      if (selector === '[data-action]') {
        return {
          tagName: 'BUTTON',
          getAttribute: () => 'nav',
          dataset: { screen: 'auth-language' }
        };
      }
      return null;
    }
  },
  preventDefault: () => {}
};

const actionEl = dummyEvent.target.closest('[data-action]');
const action = actionEl.getAttribute('data-action');
console.log(`Action detected: '${action}'`);
if (ACTION_DISPATCHER[action]) {
  ACTION_DISPATCHER[action](dummyEvent, actionEl);
  console.log(`Navigated to screen: '${store.get('currentScreen')}'`);
  if (store.get('currentScreen') === 'auth-language') {
    console.log('SUCCESS: Navigated to auth-language via ACTION_DISPATCHER[action](e)!');
  } else {
    console.error('FAIL: Screen is', store.get('currentScreen'));
    process.exit(1);
  }
} else {
  console.error('FAIL: action not in ACTION_DISPATCHER');
  process.exit(1);
}

// Test another action: create-lot
console.log('Testing create-lot dispatch...');
if (typeof ACTION_DISPATCHER['create-lot'] === 'function') {
  console.log('✓ create-lot handler is callable');
}

console.log('ALL FRONTEND TESTS PASSED!');
